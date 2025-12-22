"""
Utility functions for content library indexing
"""
import re
import logging
from typing import Optional
from sqlalchemy.orm import Session
from ..models.content_library import ContentLibrary
from ..config.database import get_db

logger = logging.getLogger(__name__)

def generate_topic_slug(topic_name: str, unit_name: Optional[str] = None, unit_number: Optional[int] = None, subject_code: Optional[str] = None) -> str:
    """
    Generate a topic slug from topic name, ALWAYS using the format: "subjectcode-unit-number-topic-name"
    when subject_code is provided. This ensures consistency across documents, videos, and topic mappings.
    
    IMPORTANT: This function is used by both:
    1. content_library table (when indexing uploaded documents/videos)
    2. topic_mappings table (when mapping university topics to PCI topics)
    
    MANDATORY FORMAT (when subject_code is provided):
        "subjectcode-unit-number-topic-name"
        Example: "bp101t-unit-1-structure-of-cell"
    
    This consistent format is CRITICAL for the application to properly find and link topics
    across content_library and topic_mappings tables. Mismatched slugs will break topic linking.
    
    Format Rules:
    - When subject_code is provided: ALWAYS use "subjectcode-unit-number-topic-name"
    - When subject_code is NOT provided but unit_number is: "unit-number-topic-name"
    - When subject_code is NOT provided but unit_name is: "unit-name-topic-name"
    - When neither is provided: "topic-name" (fallback, may have conflicts)
    
    Examples:
        generate_topic_slug("Structure of Cell", unit_number=1, subject_code="BP101T") 
            -> "bp101t-unit-1-structure-of-cell" (MANDATORY format)
        generate_topic_slug("Structure of Cell", unit_name="Unit 1", subject_code="BP101T") 
            -> "bp101t-unit-1-structure-of-cell" (extracts 1 from "Unit 1")
        generate_topic_slug("Structure of Cell", unit_number=1) 
            -> "unit-1-structure-of-cell" (no subject_code)
        generate_topic_slug("Structure of Cell") 
            -> "structure-of-cell" (fallback)
    
    Args:
        topic_name: The topic name (required)
        unit_name: Optional unit name (e.g., "Unit 1", "Introduction to Human Body")
        unit_number: Optional unit number (e.g., 1, 2) - takes priority over unit_name
        subject_code: Optional subject code (e.g., "BP101T") - should ALWAYS be provided for consistency
    
    Returns:
        A slug string in format: "subjectcode-unit-number-topic-name" (when subject_code provided)
    """
    if not topic_name:
        return ""
    
    # Build slug parts - ALWAYS follow consistent format
    slug_parts = []
    
    # 1. Subject code (MANDATORY when provided - ensures consistency)
    # CRITICAL: subject_code should ALWAYS be provided for consistency across documents, videos, and mappings
    if subject_code and subject_code.strip():
        slug_parts.append(subject_code.lower().strip())
    else:
        # Log warning if subject_code is missing (should be provided for consistency)
        logger.warning(
            f"generate_topic_slug called without subject_code for topic '{topic_name}'. "
            f"This may cause slug mismatches. Subject code should always be provided when available."
        )
    
    # 2. Unit number (extract from unit_name if not provided, or use unit_name as fallback)
    final_unit_number = None
    
    if unit_number is not None:
        final_unit_number = unit_number
    elif unit_name:
        # Try to extract unit number from unit name
        # Patterns: "Unit 1", "1:", "Unit I" -> extract number
        unit_name_lower = unit_name.lower().strip()
        
        # Try to find numeric unit number first
        num_match = re.search(r'unit\s*(\d+)', unit_name_lower)
        if num_match:
            final_unit_number = int(num_match.group(1))
        else:
            # Try pattern like "1: Title" or just "1"
            num_match = re.search(r'^(\d+)[:\s]', unit_name_lower)
            if num_match:
                final_unit_number = int(num_match.group(1))
    
    # Add unit information in consistent format
    if final_unit_number is not None:
        slug_parts.append(f"unit-{final_unit_number}")
    elif unit_name:
        # Fallback: use unit_name as slug (only if no number found)
        unit_slug = unit_name.lower()
        unit_slug = re.sub(r'[\s_]+', '-', unit_slug)
        unit_slug = re.sub(r'[^a-z0-9\-]', '', unit_slug)
        unit_slug = re.sub(r'-+', '-', unit_slug)
        unit_slug = unit_slug.strip('-')
        if unit_slug:
            slug_parts.append(unit_slug)
    
    # 3. Topic name (always included)
    topic_slug = topic_name.lower()
    topic_slug = re.sub(r'[\s_]+', '-', topic_slug)
    topic_slug = re.sub(r'[^a-z0-9\-]', '', topic_slug)
    topic_slug = re.sub(r'-+', '-', topic_slug)
    topic_slug = topic_slug.strip('-')
    
    if topic_slug:
        slug_parts.append(topic_slug)
    
    # Join all parts with hyphens
    slug = '-'.join(slug_parts)
    
    # Clean up any multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    
    return slug

def get_file_type_from_filename(filename: str) -> str:
    """
    Determine file type from filename extension.
    Returns: 'video' or 'document'
    """
    if not filename:
        return 'document'
    
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    # Video extensions
    video_extensions = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'wmv', 'm4v'}
    if ext in video_extensions:
        return 'video'
    
    # All document extensions (PDF, DOCX, DOC, TXT, MD, etc.)
    # Default to document for all non-video files
    return 'document'

def index_content_library(
    db: Session,
    topic_slug: str,
    s3_key: str,
    file_type: str,
    uploaded_via: str = 'PCI',
    topic_name: Optional[str] = None
) -> Optional[ContentLibrary]:
    """
    Index a file in the content library table.
    
    Args:
        db: Database session
        topic_slug: Topic slug (e.g., 'structure-of-cell')
        s3_key: S3 key (e.g., 'bpharm/pci/1-1/hap/unit1/structure-of-cell.mp4')
        file_type: File type ('video', 'notes', 'document')
        uploaded_via: Upload source ('PCI', 'University', etc.)
        topic_name: Human-readable topic name (e.g., 'Structure of Cell')
    
    Returns:
        ContentLibrary object if successful, None otherwise
    """
    try:
        # Check if record already exists
        existing = db.query(ContentLibrary).filter(ContentLibrary.s3_key == s3_key).first()
        if existing:
            # Update topic_name if provided and different
            if topic_name and existing.topic_name != topic_name:
                existing.topic_name = topic_name
                db.commit()
                db.refresh(existing)
            logger.info(f"Content library record already exists for s3_key: {s3_key}")
            return existing
        
        # Create new record
        content_lib = ContentLibrary(
            topic_slug=topic_slug,
            topic_name=topic_name,
            s3_key=s3_key,
            file_type=file_type,
            uploaded_via=uploaded_via
        )
        
        db.add(content_lib)
        db.commit()
        db.refresh(content_lib)
        
        logger.info(f"Successfully indexed content library: topic_slug={topic_slug}, topic_name={topic_name}, s3_key={s3_key}, file_type={file_type}")
        return content_lib
        
    except Exception as e:
        logger.error(f"Failed to index content library: {str(e)}")
        db.rollback()
        return None

def delete_content_library_by_s3_key(db: Session, s3_key: str) -> bool:
    """
    Delete a content library record by S3 key.
    
    Args:
        db: Database session
        s3_key: S3 key to delete
    
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        content_lib = db.query(ContentLibrary).filter(ContentLibrary.s3_key == s3_key).first()
        if content_lib:
            db.delete(content_lib)
            db.commit()
            logger.info(f"Successfully deleted content library record for s3_key: {s3_key}")
            return True
        else:
            logger.info(f"No content library record found for s3_key: {s3_key}")
            return False
    except Exception as e:
        logger.error(f"Failed to delete content library record: {str(e)}")
        db.rollback()
        return False

