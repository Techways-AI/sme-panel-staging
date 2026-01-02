import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..core.dual_auth import get_dual_auth_user
from ..config.database import get_db
from ..utils.s3_utils import (
    load_documents_metadata,
    load_videos_metadata,
)
from ..utils.db_utils import get_notes_by_user_id
from ..models.curriculum import UniversityCurriculum
from ..models.notes import GeneratedNotes
from ..models.content_library import ContentLibrary

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
)


def _parse_timestamp(value: str | None) -> float:
    """Parse a timestamp string into a sortable float.

    Falls back to 0 on any error so items without dates naturally sink to the end.
    """

    if not value:
        return 0.0
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).timestamp()
        except Exception:
            continue
    return 0.0


@router.get("/summary")
async def get_dashboard_summary(
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Fast summary endpoint for dashboard stats and recent items.

    This avoids multiple heavy list endpoints on the frontend by:
    - Loading documents, videos, and notes metadata directly from S3
    - Computing aggregate stats and small recent lists server‑side
    """

    try:
        user_id = auth_result.get("user_data", {}).get("sub", "anonymous")

        documents = load_documents_metadata()
        videos = load_videos_metadata()

        # Notes are stored per-user in the database; count only this user's notes
        try:
            user_notes = get_notes_by_user_id(db, user_id)
            notes_count = len(user_notes)
        except Exception as notes_exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to load notes for user %s: %s", user_id, notes_exc)
            notes_count = 0

        documents_total = len(documents)
        documents_processed = sum(1 for d in documents if d.get("processed"))
        documents_unprocessed = documents_total - documents_processed

        # Recent documents
        sorted_docs = sorted(
            documents,
            key=lambda d: _parse_timestamp(d.get("uploadDate")),
            reverse=True,
        )[:5]

        recent_documents: List[Dict[str, Any]] = []
        for doc in sorted_docs:
            folder = doc.get("folderStructure", {}) or {}
            subject = folder.get("subjectName") or "Unknown Subject"
            unit = folder.get("unitName")
            subject_label = f"{subject} - {unit}" if unit else subject

            status: str
            if doc.get("processed"):
                status = "processed"
            elif doc.get("processing"):
                status = "processing"
            else:
                status = "pending"

            recent_documents.append(
                {
                    "title": doc.get("fileName") or "Untitled Document",
                    "subject": subject_label,
                    "status": status,
                }
            )

        # Recent videos
        sorted_videos = sorted(
            videos,
            key=lambda v: _parse_timestamp(v.get("dateAdded")),
            reverse=True,
        )[:5]

        recent_videos: List[Dict[str, Any]] = []
        for video in sorted_videos:
            folder = video.get("folderStructure", {}) or {}
            subject = folder.get("subjectName") or "Unknown Subject"
            topic = folder.get("topic")
            title = topic or "Untitled Video"

            recent_videos.append(
                {
                    "title": title,
                    "subject": subject,
                    "platform": video.get("platform") or "Unknown",
                }
            )

        summary = {
            "stats": {
                "documentsTotal": documents_total,
                "documentsProcessed": documents_processed,
                "documentsUnprocessed": documents_unprocessed,
                "videos": len(videos),
                "notes": notes_count,
                # Placeholder for now – adjust when you have a source for this
                "universityContent": 0,
            },
            "recentDocuments": recent_documents,
            "recentVideos": recent_videos,
            "user": {
                "id": user_id,
            },
        }

        return summary

    except HTTPException:
        # Let FastAPI handle already created HTTPExceptions
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to build dashboard summary: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load dashboard summary") from exc


def _count_content_from_library(db: Session, uploaded_via: str, file_type: str) -> int:
    """Count content files from content_library table.
    
    Args:
        db: Database session
        uploaded_via: Filter by uploaded_via column ('PCI', 'JNTU', 'JNTUH', etc.)
                      For universities, matches if uploaded_via starts with university name
        file_type: Filter by file_type column ('document', 'video', 'notes')
    
    Returns:
        Count of files matching the criteria
    """
    try:
        uploaded_via_upper = uploaded_via.upper()
        
        # For PCI, exact match
        if uploaded_via_upper == "PCI":
            count = db.query(ContentLibrary).filter(
                ContentLibrary.uploaded_via == uploaded_via_upper,
                ContentLibrary.file_type == file_type.lower()
            ).count()
        else:
            # For universities, match if uploaded_via starts with university name
            # This handles cases like "JNTU" matching "JNTU R25" or "JNTU" matching "JNTU"
            count = db.query(ContentLibrary).filter(
                ContentLibrary.uploaded_via.like(f"{uploaded_via_upper}%"),
                ContentLibrary.file_type == file_type.lower()
            ).count()
        
        return count
    except Exception as e:
        logger.error(f"Failed to count content from library: {e}")
        return 0


def _count_unique_topics_with_content(content_list: List[Dict[str, Any]], curriculum_obj: UniversityCurriculum, aggregate_pci: bool = False) -> int:
    """Count unique topics that have content for a given curriculum.
    
    DEPRECATED: This function is kept for backward compatibility but should be replaced
    with _count_content_from_library for PCI curricula.
    
    If aggregate_pci is True and curriculum is PCI, counts all PCI content.
    Otherwise counts content matching the specific curriculum.
    """
    unique_topics = set()
    
    # Get curriculum identifier from the curriculum object
    curriculum_type = curriculum_obj.curriculum_type.lower()
    curriculum_identifier = curriculum_obj.university.lower() if curriculum_type == "university" else "pci"
    
    for item in content_list:
        folder = item.get("folderStructure", {}) or {}
        item_curriculum = folder.get("curriculum", "pci").lower()
        
        # Match curriculum based on type
        if curriculum_type == "pci" and item_curriculum in ["pci", "pci master"]:
            # For PCI, always count all PCI content (whether aggregating or not)
            topic = folder.get("topic")
            if topic:
                # Create unique key: subject + unit + topic
                subject = folder.get("subjectName", "")
                unit = folder.get("unitName", "")
                topic_key = f"{subject}::{unit}::{topic}".lower()
                unique_topics.add(topic_key)
        elif curriculum_type == "university":
            # For university curricula, match by university name
            item_university = folder.get("university", "").lower()
            if item_university and curriculum_identifier in item_university:
                topic = folder.get("topic")
                if topic:
                    subject = folder.get("subjectName", "")
                    unit = folder.get("unitName", "")
                    topic_key = f"{subject}::{unit}::{topic}".lower()
                    unique_topics.add(topic_key)
    
    return len(unique_topics)


def _count_topics_from_curriculum_data(curriculum_data: Dict[str, Any]) -> int:
    """Count topics from a single curriculum_data JSON structure.
    
    Helper function to count topics from curriculum_data structure:
    years -> semesters -> subjects -> units -> topics
    """
    total_topics = 0
    
    if not curriculum_data or not isinstance(curriculum_data, dict):
        return 0
    
    years = curriculum_data.get("years", [])
    if not isinstance(years, list):
        return 0
    
    # Count topics by iterating through the curriculum structure
    for year in years:
        if not isinstance(year, dict):
            continue
        semesters = year.get("semesters", [])
        if not isinstance(semesters, list):
            continue
            
        for semester in semesters:
            if not isinstance(semester, dict):
                continue
            subjects = semester.get("subjects", [])
            if not isinstance(subjects, list):
                continue
                
            for subject in subjects:
                if not isinstance(subject, dict):
                    continue
                units = subject.get("units", [])
                if not isinstance(units, list):
                    continue
                    
                for unit in units:
                    if not isinstance(unit, dict):
                        continue
                    topics = unit.get("topics", [])
                    if not isinstance(topics, list):
                        continue
                        
                    # Count each topic (can be string or object with 'name' property)
                    for topic in topics:
                        if isinstance(topic, str) and topic.strip():
                            # Topic is a string
                            total_topics += 1
                        elif isinstance(topic, dict) and topic.get("name"):
                            # Topic is an object with a 'name' property
                            total_topics += 1
    
    return total_topics


def _get_total_topics_from_curriculum(db: Session, curriculum_id: int) -> int:
    """Get total number of topics from curriculum data in university_curricula table.
    
    Always counts topics from curriculum_data JSON column to ensure accuracy.
    Queries the selected university curriculum by ID and counts all topics
    from the curriculum_data structure: years -> semesters -> subjects -> units -> topics
    """
    try:
        # Query curriculum by ID from university_curricula table
        curriculum_obj = db.query(UniversityCurriculum).filter(
            UniversityCurriculum.id == curriculum_id,
            UniversityCurriculum.status == "active"
        ).first()
        
        if not curriculum_obj:
            logger.warning(f"Curriculum with ID {curriculum_id} not found or inactive")
            return 0
        
        # Count topics from curriculum_data
        total_topics = _count_topics_from_curriculum_data(curriculum_obj.curriculum_data)
        
        logger.info(f"Counted {total_topics} total topics from curriculum_data for curriculum ID {curriculum_id} ({curriculum_obj.university} {curriculum_obj.regulation})")
        return total_topics
        
    except Exception as e:
        logger.error(f"Failed to get total topics from curriculum ID {curriculum_id}: {e}", exc_info=True)
        return 0


def _get_total_topics_from_all_pci_curricula(db: Session) -> int:
    """Get total number of topics from ALL PCI curricula aggregated together.
    
    Queries all active PCI curricula and counts all unique topics across
    all years, semesters, subjects, units from all PCI curricula.
    """
    try:
        # Get all active PCI curricula
        pci_curricula = db.query(UniversityCurriculum).filter(
            UniversityCurriculum.curriculum_type == "pci",
            UniversityCurriculum.status == "active"
        ).all()
        
        if not pci_curricula:
            logger.warning("No active PCI curricula found")
            return 0
        
        total_topics = 0
        
        # Count topics from each PCI curriculum
        for curriculum_obj in pci_curricula:
            topics_count = _count_topics_from_curriculum_data(curriculum_obj.curriculum_data)
            total_topics += topics_count
        
        logger.info(f"Counted {total_topics} total topics from all {len(pci_curricula)} PCI curricula")
        return total_topics
        
    except Exception as e:
        logger.error(f"Failed to get total topics from all PCI curricula: {e}", exc_info=True)
        return 0


def _get_total_topics_from_all_university_curricula(db: Session, university: str, regulation: str) -> int:
    """Get total number of topics from ALL curricula for a specific university and regulation.
    
    Queries all active curricula matching the university and regulation, and counts all topics
    across all years, semesters, subjects, units from all matching curricula.
    
    This aggregates all curricula for the same university/regulation, similar to how PCI works.
    """
    try:
        # Get all active curricula for this university and regulation
        university_curricula = db.query(UniversityCurriculum).filter(
            UniversityCurriculum.curriculum_type == "university",
            UniversityCurriculum.university == university,
            UniversityCurriculum.regulation == regulation,
            UniversityCurriculum.status == "active"
        ).all()
        
        if not university_curricula:
            logger.warning(f"No active curricula found for {university} {regulation}")
            return 0
        
        total_topics = 0
        
        # Count topics from each curriculum
        for curriculum_obj in university_curricula:
            topics_count = _count_topics_from_curriculum_data(curriculum_obj.curriculum_data)
            total_topics += topics_count
        
        logger.info(f"Counted {total_topics} total topics from all {len(university_curricula)} curricula for {university} {regulation}")
        return total_topics
        
    except Exception as e:
        logger.error(f"Failed to get total topics from all university curricula for {university} {regulation}: {e}", exc_info=True)
        return 0


def _count_unique_topics_with_notes(db: Session, curriculum_obj: UniversityCurriculum, aggregate_pci: bool = False) -> int:
    """Count unique topics that have notes for a given curriculum.
    
    For PCI curricula, counts notes from content_library table.
    For university curricula, counts from GeneratedNotes table (legacy).
    """
    try:
        curriculum_type = curriculum_obj.curriculum_type.lower()
        
        # For PCI, count from content_library table
        if curriculum_type == "pci":
            return _count_content_from_library(db, "PCI", "notes")
        
        # For university curricula, use legacy method (from GeneratedNotes table)
        # Get all notes from database
        all_notes = db.query(GeneratedNotes).all()
        
        unique_topics = set()
        curriculum_identifier = curriculum_obj.university.lower()
        
        for note in all_notes:
            # Notes have subject_name, unit_name, and topic fields
            subject = note.subject_name or ""
            unit = note.unit_name or ""
            topic = note.topic or ""
            
            if topic:
                # TODO: Add curriculum matching for university notes when curriculum field is added
                topic_key = f"{subject}::{unit}::{topic}".lower()
                unique_topics.add(topic_key)
        
        return len(unique_topics)
    except Exception as e:
        logger.error(f"Failed to count notes topics: {e}")
        return 0


@router.get("/content-coverage")
async def get_content_coverage(
    curriculum_id: int = Query(..., description="Curriculum ID from curriculum manager"),
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get content coverage statistics for a specific curriculum.
    
    Queries the university_curricula table for the selected curriculum and counts
    total topics from the curriculum_data JSON column. Returns counts of documents,
    videos, and notes, along with total topics and coverage percentages.
    
    For PCI Master curricula, aggregates ALL PCI curricula together.
    For university curricula, aggregates ALL curricula for the same university and regulation.
    This ensures consistent counting across all years, semesters, subjects, units, and topics.
    
    The total topics count is always calculated from curriculum_data by iterating
    through: years -> semesters -> subjects -> units -> topics
    """
    try:
        # Get curriculum object
        curriculum_obj = db.query(UniversityCurriculum).filter(
            UniversityCurriculum.id == curriculum_id,
            UniversityCurriculum.status == "active"
        ).first()
        
        if not curriculum_obj:
            raise HTTPException(status_code=404, detail=f"Curriculum with ID {curriculum_id} not found or inactive")
        
        # Check if this is a PCI curriculum - if so, aggregate ALL PCI curricula
        is_pci = curriculum_obj.curriculum_type.lower() == "pci"
        aggregate_pci = is_pci
        
        # Count content files from content_library table
        # For PCI, count directly from content_library table by uploaded_via='PCI' and file_type
        if aggregate_pci:
            # Count from content_library table for PCI
            documents_topics_count = _count_content_from_library(db, "PCI", "document")
            videos_topics_count = _count_content_from_library(db, "PCI", "video")
            notes_topics_count = _count_content_from_library(db, "PCI", "notes")
        else:
            # For university curricula, count from content_library table by uploaded_via matching university name
            uploaded_via = curriculum_obj.university.upper()
            documents_topics_count = _count_content_from_library(db, uploaded_via, "document")
            videos_topics_count = _count_content_from_library(db, uploaded_via, "video")
            notes_topics_count = _count_content_from_library(db, uploaded_via, "notes")
        
        # Get total topics
        # For PCI Master, aggregate ALL PCI curricula to get total count
        # For universities, aggregate ALL curricula for the same university and regulation
        if aggregate_pci:
            total_topics = _get_total_topics_from_all_pci_curricula(db)
            logger.info(f"PCI Master selected - aggregated total topics from all PCI curricula: {total_topics}")
        else:
            # Aggregate all curricula for the same university and regulation
            total_topics = _get_total_topics_from_all_university_curricula(
                db, 
                curriculum_obj.university, 
                curriculum_obj.regulation
            )
            logger.info(f"{curriculum_obj.university} {curriculum_obj.regulation} selected - aggregated total topics from all matching curricula: {total_topics}")
        
        # Calculate percentages
        documents_percentage = round((documents_topics_count / total_topics * 100) if total_topics > 0 else 0, 1)
        videos_percentage = round((videos_topics_count / total_topics * 100) if total_topics > 0 else 0, 1)
        notes_percentage = round((notes_topics_count / total_topics * 100) if total_topics > 0 else 0, 1)
        
        # Calculate overall coverage (average of all three)
        overall_percentage = round((documents_percentage + videos_percentage + notes_percentage) / 3, 1)
        
        return {
            "documents": {
                "count": documents_topics_count,
                "total": total_topics,
                "percentage": documents_percentage,
            },
            "videos": {
                "count": videos_topics_count,
                "total": total_topics,
                "percentage": videos_percentage,
            },
            "notes": {
                "count": notes_topics_count,
                "total": total_topics,
                "percentage": notes_percentage,
            },
            "overall": overall_percentage,
            "curriculum": {
                "id": curriculum_obj.id,
                "display_name": f"{curriculum_obj.university} {curriculum_obj.regulation}" if curriculum_obj.curriculum_type == "university" else "PCI Master",
                "curriculum_type": curriculum_obj.curriculum_type,
            },
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get content coverage: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load content coverage") from exc


def _count_content_by_subject(db: Session, uploaded_via: str, file_type: str, subject_code: str) -> int:
    """Count content files for a specific subject from content_library table.
    
    Args:
        db: Database session
        uploaded_via: Filter by uploaded_via column ('PCI', 'JNTU', 'JNTUH', etc.)
                      For universities, matches if uploaded_via starts with university name
        file_type: Filter by file_type column ('document', 'video', 'notes')
        subject_code: Subject code (e.g., 'BP101T') - topic_slug starts with this
    
    Returns:
        Count of files matching the criteria
    """
    try:
        # Topic slugs follow format: "subjectcode-unit-number-topic-name" or "subjectcode-unit-name-topic-name"
        # So we filter by topic_slug starting with subject_code (case-insensitive)
        subject_code_lower = subject_code.lower()
        uploaded_via_upper = uploaded_via.upper()
        
        # For PCI, exact match
        if uploaded_via_upper == "PCI":
            count = db.query(ContentLibrary).filter(
                ContentLibrary.uploaded_via == uploaded_via_upper,
                ContentLibrary.file_type == file_type.lower(),
                ContentLibrary.topic_slug.like(f"{subject_code_lower}%")
            ).count()
        else:
            # For universities, match if uploaded_via starts with university name
            # This handles cases like "JNTU" matching "JNTU R25" or "JNTU" matching "JNTU"
            count = db.query(ContentLibrary).filter(
                ContentLibrary.uploaded_via.like(f"{uploaded_via_upper}%"),
                ContentLibrary.file_type == file_type.lower(),
                ContentLibrary.topic_slug.like(f"{subject_code_lower}%")
            ).count()
        
        return count
    except Exception as e:
        logger.error(f"Failed to count content by subject: {e}")
        return 0


@router.get("/subject-coverage")
async def get_subject_coverage(
    curriculum_id: int = Query(..., description="Curriculum ID from curriculum manager"),
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get subject-level coverage statistics for a specific curriculum.
    
    Returns subjects with their year, semester, topic counts, and coverage percentages
    for documents, videos, and notes. 
    
    For PCI Master, aggregates all PCI curricula.
    For university curricula, aggregates all curricula for the same university and regulation.
    This ensures all subjects from all matching curricula are included.
    """
    try:
        # Get curriculum object
        curriculum_obj = db.query(UniversityCurriculum).filter(
            UniversityCurriculum.id == curriculum_id,
            UniversityCurriculum.status == "active"
        ).first()
        
        if not curriculum_obj:
            raise HTTPException(status_code=404, detail=f"Curriculum with ID {curriculum_id} not found or inactive")
        
        # Check if this is a PCI curriculum
        is_pci = curriculum_obj.curriculum_type.lower() == "pci"
        uploaded_via = "PCI" if is_pci else curriculum_obj.university.upper()
        
        subjects_list = []
        logger.info(f"Getting subject coverage for curriculum ID {curriculum_id}, type: {curriculum_obj.curriculum_type}, uploaded_via: {uploaded_via}")
        
        if is_pci:
            # For PCI Master, aggregate ALL PCI curricula
            matching_curricula = db.query(UniversityCurriculum).filter(
                UniversityCurriculum.curriculum_type == "pci",
                UniversityCurriculum.status == "active"
            ).all()
        else:
            # For university curricula, aggregate ALL curricula for the same university and regulation
            matching_curricula = db.query(UniversityCurriculum).filter(
                UniversityCurriculum.curriculum_type == "university",
                UniversityCurriculum.university == curriculum_obj.university,
                UniversityCurriculum.regulation == curriculum_obj.regulation,
                UniversityCurriculum.status == "active"
            ).all()
        
        # Track subjects by code+year+semester to show all occurrences
        # Use a composite key to handle same subject in different years/semesters
        subjects_map = {}
        
        if is_pci or len(matching_curricula) > 0:
            for curriculum in matching_curricula:
                curriculum_data = curriculum.curriculum_data
                if not curriculum_data or not isinstance(curriculum_data, dict):
                    continue
                
                years = curriculum_data.get("years", [])
                
                for year in years:
                    if not isinstance(year, dict):
                        continue
                    year_num = year.get("year", 0)
                    semesters = year.get("semesters", [])
                    
                    for semester in semesters:
                        if not isinstance(semester, dict):
                            continue
                        semester_num = semester.get("semester", 0)
                        subjects = semester.get("subjects", [])
                        
                        for subject in subjects:
                            if not isinstance(subject, dict):
                                continue
                            
                            subject_code = subject.get("code", "")
                            subject_name = subject.get("name", "")
                            
                            if not subject_code:
                                continue
                            
                            # Convert semester number (1-8) to display format (Year 1-4, Semester 1-2)
                            display_year = ((semester_num - 1) // 2) + 1 if semester_num > 0 else year_num
                            display_semester = ((semester_num - 1) % 2) + 1 if semester_num > 0 else 1
                            
                            # Create composite key: code-year-semester to handle same subject in different contexts
                            # But if same subject appears in same year/semester, merge topics
                            composite_key = f"{subject_code}-{display_year}-{display_semester}"
                            
                            if composite_key not in subjects_map:
                                # Count topics for this subject
                                total_topics = 0
                                units = subject.get("units", [])
                                for unit in units:
                                    if isinstance(unit, dict):
                                        topics = unit.get("topics", [])
                                        for topic in topics:
                                            if isinstance(topic, str) and topic.strip():
                                                total_topics += 1
                                            elif isinstance(topic, dict) and topic.get("name"):
                                                total_topics += 1
                                
                                subjects_map[composite_key] = {
                                    "code": subject_code,
                                    "name": subject_name,
                                    "year": display_year,
                                    "semester": display_semester,
                                    "topics": total_topics,
                                }
                            else:
                                # If subject already exists in same year/semester, add topics to existing count
                                units = subject.get("units", [])
                                for unit in units:
                                    if isinstance(unit, dict):
                                        topics = unit.get("topics", [])
                                        for topic in topics:
                                            if isinstance(topic, str) and topic.strip():
                                                subjects_map[composite_key]["topics"] += 1
                                            elif isinstance(topic, dict) and topic.get("name"):
                                                subjects_map[composite_key]["topics"] += 1
        
        # Count content for each subject from content_library
        logger.info(f"Processing {len(subjects_map)} subjects for subject coverage")
        for composite_key, subject_data in subjects_map.items():
            subject_code = subject_data["code"]
            try:
                docs_count = _count_content_by_subject(db, uploaded_via, "document", subject_code)
                videos_count = _count_content_by_subject(db, uploaded_via, "video", subject_code)
                notes_count = _count_content_by_subject(db, uploaded_via, "notes", subject_code)
                
                total_topics = subject_data["topics"]
                
                # Calculate percentages
                docs_percentage = round((docs_count / total_topics * 100) if total_topics > 0 else 0, 0)
                videos_percentage = round((videos_count / total_topics * 100) if total_topics > 0 else 0, 0)
                notes_percentage = round((notes_count / total_topics * 100) if total_topics > 0 else 0, 0)
                
                subjects_list.append({
                    "code": subject_data["code"],
                    "name": subject_data["name"],
                    "year": subject_data["year"],
                    "semester": subject_data["semester"],
                    "topics": total_topics,
                    "docs": int(docs_percentage),
                    "videos": int(videos_percentage),
                    "notes": int(notes_percentage),
                })
            except Exception as e:
                logger.error(f"Error processing subject {subject_code}: {e}")
                # Continue processing other subjects even if one fails
                continue
        
        logger.info(f"Returning {len(subjects_list)} subjects in subject coverage response")
        return {
            "subjects": subjects_list,
            "curriculum": {
                "id": curriculum_obj.id,
                "display_name": f"{curriculum_obj.university} {curriculum_obj.regulation}" if curriculum_obj.curriculum_type == "university" else "PCI Master",
                "curriculum_type": curriculum_obj.curriculum_type,
            },
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get subject coverage: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load subject coverage") from exc


def _count_unique_topics_with_content_by_year_semester(
    db: Session, 
    uploaded_via: str, 
    file_type: str, 
    subject_codes: List[str]
) -> int:
    """Count unique topics that have content for a specific year/semester from content_library table.
    
    This counts unique topic_slugs (not files) to get accurate coverage percentage.
    
    Args:
        db: Database session
        uploaded_via: Filter by uploaded_via column
        file_type: Filter by file_type column ('document', 'video', 'notes')
        subject_codes: List of subject codes for this year/semester
    
    Returns:
        Count of unique topics that have content
    """
    try:
        if not subject_codes:
            return 0
        
        uploaded_via_upper = uploaded_via.upper()
        file_type_lower = file_type.lower()
        
        # Build query with OR conditions for all subject codes
        if uploaded_via_upper == "PCI":
            query = db.query(ContentLibrary.topic_slug).filter(
                ContentLibrary.uploaded_via == uploaded_via_upper,
                ContentLibrary.file_type == file_type_lower
            )
        else:
            query = db.query(ContentLibrary.topic_slug).filter(
                ContentLibrary.uploaded_via.like(f"{uploaded_via_upper}%"),
                ContentLibrary.file_type == file_type_lower
            )
        
        # Filter by subject codes (topic_slug starts with any subject code)
        subject_filters = [
            ContentLibrary.topic_slug.like(f"{code.lower()}%") 
            for code in subject_codes
        ]
        query = query.filter(or_(*subject_filters))
        
        # Count distinct topic_slugs
        return query.distinct().count()
    except Exception as e:
        logger.error(f"Failed to count unique topics by year/semester: {e}")
        return 0


@router.get("/year-coverage")
async def get_year_coverage(
    curriculum_id: int = Query(..., description="Curriculum ID from curriculum manager"),
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get year-wise coverage statistics for a specific curriculum.
    
    Returns coverage percentages for each year and semester, calculated from:
    - Total topics from curriculum_data
    - Content counts from content_library table
    
    For PCI Master, aggregates all PCI curricula.
    For university curricula, aggregates all curricula for the same university and regulation.
    """
    try:
        # Get curriculum object
        curriculum_obj = db.query(UniversityCurriculum).filter(
            UniversityCurriculum.id == curriculum_id,
            UniversityCurriculum.status == "active"
        ).first()
        
        if not curriculum_obj:
            raise HTTPException(status_code=404, detail=f"Curriculum with ID {curriculum_id} not found or inactive")
        
        # Check if this is a PCI curriculum
        is_pci = curriculum_obj.curriculum_type.lower() == "pci"
        uploaded_via = "PCI" if is_pci else curriculum_obj.university.upper()
        uploaded_via_upper = uploaded_via.upper()
        
        # Get matching curricula (all PCI or all matching university/regulation)
        if is_pci:
            matching_curricula = db.query(UniversityCurriculum).filter(
                UniversityCurriculum.curriculum_type == "pci",
                UniversityCurriculum.status == "active"
            ).all()
        else:
            matching_curricula = db.query(UniversityCurriculum).filter(
                UniversityCurriculum.curriculum_type == "university",
                UniversityCurriculum.university == curriculum_obj.university,
                UniversityCurriculum.regulation == curriculum_obj.regulation,
                UniversityCurriculum.status == "active"
            ).all()
        
        # Track year-semester data: year -> semester -> {topics, subject_codes}
        year_semester_data: Dict[int, Dict[int, Dict[str, Any]]] = {}
        
        # Aggregate curriculum data
        for curriculum in matching_curricula:
            curriculum_data = curriculum.curriculum_data
            if not curriculum_data or not isinstance(curriculum_data, dict):
                continue
            
            years = curriculum_data.get("years", [])
            
            for year in years:
                if not isinstance(year, dict):
                    continue
                year_num = year.get("year", 0)
                semesters = year.get("semesters", [])
                
                for semester in semesters:
                    if not isinstance(semester, dict):
                        continue
                    semester_num = semester.get("semester", 0)
                    
                    # Convert semester number (1-8) to display format (Year 1-4, Semester 1-2)
                    display_year = ((semester_num - 1) // 2) + 1 if semester_num > 0 else year_num
                    display_semester = ((semester_num - 1) % 2) + 1 if semester_num > 0 else 1
                    
                    # Initialize year if not exists
                    if display_year not in year_semester_data:
                        year_semester_data[display_year] = {}
                    
                    # Initialize semester if not exists
                    if display_semester not in year_semester_data[display_year]:
                        year_semester_data[display_year][display_semester] = {
                            "topics": 0,
                            "subject_codes": set()
                        }
                    
                    # Count topics and collect subject codes
                    subjects = semester.get("subjects", [])
                    for subject in subjects:
                        if not isinstance(subject, dict):
                            continue
                        
                        subject_code = subject.get("code", "")
                        if subject_code:
                            year_semester_data[display_year][display_semester]["subject_codes"].add(subject_code)
                        
                        units = subject.get("units", [])
                        for unit in units:
                            if isinstance(unit, dict):
                                topics = unit.get("topics", [])
                                for topic in topics:
                                    if isinstance(topic, str) and topic.strip():
                                        year_semester_data[display_year][display_semester]["topics"] += 1
                                    elif isinstance(topic, dict) and topic.get("name"):
                                        year_semester_data[display_year][display_semester]["topics"] += 1
        
        # Calculate coverage for each year
        year_coverage_list = []
        
        # Sort years
        sorted_years = sorted(year_semester_data.keys())
        
        for year_num in sorted_years:
            semester_data = year_semester_data[year_num]
            
            # Get semester 1 and 2 data
            sem1_topics = semester_data.get(1, {}).get("topics", 0)
            sem1_subject_codes = list(semester_data.get(1, {}).get("subject_codes", set()))
            
            sem2_topics = semester_data.get(2, {}).get("topics", 0)
            sem2_subject_codes = list(semester_data.get(2, {}).get("subject_codes", set()))
            
            total_year_topics = sem1_topics + sem2_topics
            
            # Helper function to get unique topics with content for a semester
            def get_unique_topics_with_content(subject_codes_list):
                """Get set of unique topic_slugs that have ANY content (documents OR videos OR notes)."""
                topics_set = set()
                
                if not subject_codes_list:
                    return topics_set
                
                # Build base query filter for uploaded_via
                uploaded_via_filter = (
                    ContentLibrary.uploaded_via == uploaded_via_upper
                    if uploaded_via_upper == "PCI"
                    else ContentLibrary.uploaded_via.like(f"{uploaded_via_upper}%")
                )
                
                # Build subject code filters
                subject_filters = [
                    ContentLibrary.topic_slug.like(f"{code.lower()}%") 
                    for code in subject_codes_list
                ]
                
                # Query for all content types at once (more efficient)
                query = db.query(ContentLibrary.topic_slug).filter(
                    uploaded_via_filter,
                    or_(*subject_filters)
                ).distinct()
                
                topics_set.update([row[0] for row in query.all()])
                
                return topics_set
            
            # Get unique topics with content for each semester
            sem1_topics_with_content = get_unique_topics_with_content(sem1_subject_codes)
            sem2_topics_with_content = get_unique_topics_with_content(sem2_subject_codes)
            
            # Calculate percentages based on unique topics with content
            sem1_topics_count = len(sem1_topics_with_content)
            sem2_topics_count = len(sem2_topics_with_content)
            total_year_topics_with_content = len(sem1_topics_with_content.union(sem2_topics_with_content))
            
            sem1_percentage = round((sem1_topics_count / sem1_topics * 100) if sem1_topics > 0 else 0, 0)
            sem2_percentage = round((sem2_topics_count / sem2_topics * 100) if sem2_topics > 0 else 0, 0)
            overall_percentage = round((total_year_topics_with_content / total_year_topics * 100) if total_year_topics > 0 else 0, 0)
            
            year_coverage_list.append({
                "year": f"Year {year_num}",
                "year_num": year_num,
                "semester1": int(sem1_percentage),
                "semester2": int(sem2_percentage),
                "percentage": int(overall_percentage),
            })
        
        return {
            "year_coverage": year_coverage_list,
            "curriculum": {
                "id": curriculum_obj.id,
                "display_name": f"{curriculum_obj.university} {curriculum_obj.regulation}" if curriculum_obj.curriculum_type == "university" else "PCI Master",
                "curriculum_type": curriculum_obj.curriculum_type,
            },
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get year coverage: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load year coverage") from exc
