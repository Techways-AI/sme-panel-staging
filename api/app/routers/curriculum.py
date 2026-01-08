from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import json
import os
from ..config.database import get_db
from ..config.settings import DATA_DIR
from ..models.curriculum import UniversityCurriculum
from ..models.topic_mapping import TopicMapping
from ..utils.content_library_utils import generate_topic_slug
from ..routers.auth import get_current_user

router = APIRouter()

# Pydantic models for request/response
class CurriculumSubject(BaseModel):
    code: str
    name: str
    type: str
    category: Optional[str] = None
    units: List[Dict[str, Any]] = []

class CurriculumYearSemester(BaseModel):
    year: int
    semester: int
    subjects: List[CurriculumSubject] = []

class CurriculumData(BaseModel):
    university: Optional[str] = None
    regulation: Optional[str] = None
    course: str
    year: Optional[int] = None
    semester: Optional[int] = None
    subjects: Optional[List[CurriculumSubject]] = None
    years: Optional[List[Dict[str, Any]]] = None  # Alternative format

class CurriculumCreateRequest(BaseModel):
    curriculum_type: str = "university"  # "university" or "pci"
    university: Optional[str] = None
    regulation: Optional[str] = None
    course: str
    effective_year: Optional[str] = None
    curriculum_data: CurriculumData
    auto_map_pci: bool = False

class CurriculumResponse(BaseModel):
    id: int
    university: Optional[str]
    regulation: Optional[str]
    course: str
    effective_year: Optional[str]
    curriculum_type: str
    stats: Optional[Dict[str, Any]]
    status: str
    created_at: str
    updated_at: Optional[str]
    display_name: str

class CurriculumListResponse(BaseModel):
    curricula: List[CurriculumResponse]
    total: int

class CurriculumBatchCreateRequest(BaseModel):
    items: List[CurriculumCreateRequest]

class CurriculumBatchItemResult(BaseModel):
    index: int
    success: bool
    id: Optional[int] = None
    display_name: Optional[str] = None
    error: Optional[str] = None

class CurriculumBatchResponse(BaseModel):
    results: List[CurriculumBatchItemResult]
    inserted: int

def normalize_curriculum_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize curriculum data from different formats to a standard structure.
    Handles both:
    1. Format with year/semester at root: {year: 1, semester: 1, subjects: [...]}
    2. Format with years array: {years: [{year: 1, semesters: [{semester: 1, subjects: [...]}]}]}
    """
    normalized = {
        "years": []
    }
    
    # If data has year/semester at root (user's format)
    if "year" in data and "semester" in data and "subjects" in data:
        year_num = data["year"]
        semester_num = data["semester"]
        subjects = data.get("subjects", [])
        
        # Find or create year
        year_obj = next((y for y in normalized["years"] if y["year"] == year_num), None)
        if not year_obj:
            year_obj = {"year": year_num, "semesters": []}
            normalized["years"].append(year_obj)
        
        # Add semester
        semester_obj = {
            "semester": semester_num,
            "subjects": subjects
        }
        year_obj["semesters"].append(semester_obj)
        
        # Preserve other fields
        if "university" in data:
            normalized["university"] = data["university"]
        if "regulation" in data:
            normalized["regulation"] = data["regulation"]
        if "course" in data:
            normalized["course"] = data["course"]
    
    # If data has years array (modal's expected format)
    elif "years" in data and isinstance(data["years"], list):
        normalized["years"] = data["years"]
        if "university" in data:
            normalized["university"] = data["university"]
        if "regulation" in data:
            normalized["regulation"] = data["regulation"]
        if "course" in data:
            normalized["course"] = data["course"]
    
    return normalized

def calculate_stats(curriculum_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate statistics from curriculum data.
    
    Revert to the original behavior:
    - years: shows the user-provided year when only one year exists; otherwise the count of years.
    - semesters: shows the user-provided semester when only one semester exists; otherwise the count of semesters.
    - No semester mapping (odd/even) and no extra detail fields.
    """
    stats = {
        "years": 0,
        "semesters": 0,
        "subjects": 0,
        "units": 0,
        "topics": 0,
        "theory": 0,
        "practical": 0,
        "electives": 0
    }
    
    years = curriculum_data.get("years", [])
    
    # years: if only one year object, display that year value; otherwise count how many year objects
    if len(years) == 1:
        stats["years"] = years[0].get("year", 0)
    else:
        stats["years"] = len(years)
    
    total_semesters_count = 0
    
    for year in years:
        semesters = year.get("semesters", [])
        total_semesters_count += len(semesters)
        
        for semester in semesters:
            subjects = semester.get("subjects", [])
            stats["subjects"] += len(subjects)
            
            for subject in subjects:
                subject_type = subject.get("type", "").lower()
                if "practical" in subject_type:
                    stats["practical"] += 1
                elif "elective" in subject.get("name", "").lower():
                    stats["electives"] += 1
                else:
                    stats["theory"] += 1
                
                units = subject.get("units", [])
                stats["units"] += len(units)
                
                for unit in units:
                    topics = unit.get("topics", [])
                    stats["topics"] += len(topics)
    
    # semesters: if only one semester total, show that semester number; otherwise show count
    if len(years) == 1 and len(years[0].get("semesters", [])) == 1:
        stats["semesters"] = years[0]["semesters"][0].get("semester", 0)
    else:
        stats["semesters"] = total_semesters_count
    
    return stats

def save_curriculum_to_file(curriculum_id: str, data: Dict[str, Any]) -> str:
    """Save curriculum data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    file_path = os.path.join(DATA_DIR, f"curriculum_{curriculum_id}.json")
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return file_path

def load_all_curricula_from_files() -> List[Dict[str, Any]]:
    """Load all curricula from JSON files"""
    curricula = []
    
    if not os.path.exists(DATA_DIR):
        return curricula
    
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("curriculum_") and filename.endswith(".json"):
            file_path = os.path.join(DATA_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    curricula.append(data)
            except Exception as e:
                print(f"Error loading curriculum file {filename}: {e}")
    
    return curricula

@router.post("/api/curriculum/validate", response_model=Dict[str, Any])
async def validate_curriculum(
    request: CurriculumCreateRequest,
    # Authentication is optional for validation
):
    """Validate curriculum data structure"""
    try:
        # Normalize the data
        data_dict = request.curriculum_data.model_dump()
        normalized = normalize_curriculum_data(data_dict)
        
        # Validate structure
        errors = []
        warnings = []
        
        if not normalized.get("years"):
            errors.append({
                "type": "error",
                "location": "root",
                "issue": '"years" array is required'
            })
        else:
            for year_idx, year in enumerate(normalized["years"]):
                if "year" not in year:
                    errors.append({
                        "type": "error",
                        "location": f"years[{year_idx}]",
                        "issue": '"year" field is required'
                    })
                
                if "semesters" not in year or not isinstance(year["semesters"], list):
                    errors.append({
                        "type": "error",
                        "location": f"years[{year_idx}]",
                        "issue": '"semesters" array is required'
                    })
                else:
                    for sem_idx, semester in enumerate(year["semesters"]):
                        if "semester" not in semester:
                            errors.append({
                                "type": "error",
                                "location": f"years[{year_idx}].semesters[{sem_idx}]",
                                "issue": '"semester" field is required'
                            })
                        
                        subjects = semester.get("subjects", [])
                        if not subjects:
                            warnings.append({
                                "type": "warning",
                                "location": f"years[{year_idx}].semesters[{sem_idx}]",
                                "issue": "No subjects found in this semester"
                            })
                        else:
                            for subj_idx, subject in enumerate(subjects):
                                if not subject.get("code"):
                                    errors.append({
                                        "type": "error",
                                        "location": f"years[{year_idx}].semesters[{sem_idx}].subjects[{subj_idx}]",
                                        "issue": '"code" field is required for each subject'
                                    })
                                if not subject.get("name"):
                                    errors.append({
                                        "type": "error",
                                        "location": f"years[{year_idx}].semesters[{sem_idx}].subjects[{subj_idx}]",
                                        "issue": '"name" field is required for each subject'
                                    })
                                
                                units = subject.get("units", [])
                                if not units:
                                    warnings.append({
                                        "type": "warning",
                                        "location": f"years[{year_idx}].semesters[{sem_idx}].subjects[{subj_idx}]",
                                        "issue": f'Subject "{subject.get("name", subject.get("code"))}" has no units'
                                    })
                                else:
                                    for unit_idx, unit in enumerate(units):
                                        topics = unit.get("topics", [])
                                        if not topics:
                                            warnings.append({
                                                "type": "warning",
                                                "location": f"years[{year_idx}].semesters[{sem_idx}].subjects[{subj_idx}].units[{unit_idx}]",
                                                "issue": f'Unit {unit.get("number", unit_idx + 1)} has no topics'
                                            })
        
        # Calculate stats if no critical errors
        stats = None
        if not any(e["type"] == "error" for e in errors):
            stats = calculate_stats(normalized)
        
        return {
            "valid": len([e for e in errors if e["type"] == "error"]) == 0,
            "errors": errors,
            "warnings": warnings,
            "stats": stats,
            "normalized_data": normalized
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )

@router.post("/api/curriculum", response_model=CurriculumResponse)
async def create_curriculum(
    request: CurriculumCreateRequest,
    db: Session = Depends(get_db),
    # Make authentication optional for now - can be enabled later
    # current_user = Depends(get_current_user)
):
    """Create a new university curriculum"""
    try:
        # Normalize curriculum data
        data_dict = request.curriculum_data.model_dump()
        normalized = normalize_curriculum_data(data_dict)
        
        # Calculate stats
        stats = calculate_stats(normalized)
        
        # Create curriculum record (ID will be auto-generated by database)
        curriculum = UniversityCurriculum(
            university=request.university if request.curriculum_type == "university" else "PCI",
            regulation=request.regulation if request.curriculum_type == "university" else "Master",
            course=request.course,
            effective_year=request.effective_year,
            curriculum_type=request.curriculum_type,
            curriculum_data=normalized,
            stats=stats,
            status="active",
            created_by=None  # current_user.username if current_user else None
        )
        
        # Save to database
        db.add(curriculum)
        db.commit()
        db.refresh(curriculum)
        
        # Also save to JSON file for backup/compatibility
        save_curriculum_to_file(str(curriculum.id), {
            "id": curriculum.id,
            "university": curriculum.university,
            "regulation": curriculum.regulation,
            "course": curriculum.course,
            "effective_year": curriculum.effective_year,
            "curriculum_type": curriculum.curriculum_type,
            "curriculum_data": normalized,
            "stats": stats,
            "status": curriculum.status,
            "created_at": curriculum.created_at.isoformat() if curriculum.created_at else None,
            "updated_at": curriculum.updated_at.isoformat() if curriculum.updated_at else None,
        })
        
        # Update curricula index
        update_curricula_index(str(curriculum.id), curriculum)
        
        display_name = f"{curriculum.university} {curriculum.regulation}" if request.curriculum_type == "university" else "PCI Master"
        
        return CurriculumResponse(
            id=curriculum.id,
            university=curriculum.university,
            regulation=curriculum.regulation,
            course=curriculum.course,
            effective_year=curriculum.effective_year,
            curriculum_type=curriculum.curriculum_type,
            stats=curriculum.stats,
            status=curriculum.status,
            created_at=curriculum.created_at.isoformat() if curriculum.created_at else "",
            updated_at=curriculum.updated_at.isoformat() if curriculum.updated_at else None,
            display_name=display_name
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create curriculum: {str(e)}"
        )

@router.post("/api/curriculum/batch", response_model=CurriculumBatchResponse)
async def create_curriculum_batch(
    request: CurriculumBatchCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Create multiple curricula in one call.
    Uses the same normalization/stats logic as the single create endpoint.
    Partial success is allowed; results array indicates per-item status.
    """
    results: List[Dict[str, Any]] = []
    inserted = 0

    for idx, item in enumerate(request.items):
        try:
            data_dict = item.curriculum_data.model_dump()
            normalized = normalize_curriculum_data(data_dict)
            stats = calculate_stats(normalized)

            curriculum = UniversityCurriculum(
                university=item.university if item.curriculum_type == "university" else "PCI",
                regulation=item.regulation if item.curriculum_type == "university" else "Master",
                course=item.course,
                effective_year=item.effective_year,
                curriculum_type=item.curriculum_type,
                curriculum_data=normalized,
                stats=stats,
                status="active",
                created_by=None,
            )

            db.add(curriculum)
            db.commit()
            db.refresh(curriculum)

            # Save backup file and update index
            save_curriculum_to_file(str(curriculum.id), {
                "id": curriculum.id,
                "university": curriculum.university,
                "regulation": curriculum.regulation,
                "course": curriculum.course,
                "effective_year": curriculum.effective_year,
                "curriculum_type": curriculum.curriculum_type,
                "curriculum_data": normalized,
                "stats": stats,
                "status": curriculum.status,
                "created_at": curriculum.created_at.isoformat() if curriculum.created_at else None,
                "updated_at": curriculum.updated_at.isoformat() if curriculum.updated_at else None,
            })
            update_curricula_index(str(curriculum.id), curriculum)

            display_name = f"{curriculum.university} {curriculum.regulation}" if item.curriculum_type == "university" else "PCI Master"
            results.append({
                "index": idx,
                "success": True,
                "id": curriculum.id,
                "display_name": display_name,
            })
            inserted += 1
        except Exception as e:
            db.rollback()
            results.append({
                "index": idx,
                "success": False,
                "error": str(e),
            })

    return {
        "results": results,
        "inserted": inserted,
    }

@router.get("/api/curriculum", response_model=CurriculumListResponse)
async def list_curricula(
    curriculum_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all curricula"""
    try:
        query = db.query(UniversityCurriculum)
        
        if curriculum_type:
            query = query.filter(UniversityCurriculum.curriculum_type == curriculum_type)
        
        curricula = query.filter(UniversityCurriculum.status == "active").all()
        
        curriculum_responses = []
        for curriculum in curricula:
            display_name = f"{curriculum.university} {curriculum.regulation}" if curriculum.curriculum_type == "university" else "PCI Master"
            curriculum_responses.append(CurriculumResponse(
                id=curriculum.id,
                university=curriculum.university,
                regulation=curriculum.regulation,
                course=curriculum.course,
                effective_year=curriculum.effective_year,
                curriculum_type=curriculum.curriculum_type,
                stats=curriculum.stats,
                status=curriculum.status,
                created_at=curriculum.created_at.isoformat() if curriculum.created_at else "",
                updated_at=curriculum.updated_at.isoformat() if curriculum.updated_at else None,
                display_name=display_name
            ))
        
        return CurriculumListResponse(
            curricula=curriculum_responses,
            total=len(curriculum_responses)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list curricula: {str(e)}"
        )

@router.get("/api/curriculum/batch")
async def get_curricula_batch(
    ids: str,  # Comma-separated curriculum IDs
    db: Session = Depends(get_db)
):
    """Get multiple curricula by IDs in a single request"""
    try:
        curriculum_ids = [int(id.strip()) for id in ids.split(",") if id.strip()]
        
        if not curriculum_ids:
            return {"curricula": []}
        
        curricula = db.query(UniversityCurriculum).filter(
            UniversityCurriculum.id.in_(curriculum_ids)
        ).all()
        
        results = []
        for curriculum in curricula:
            display_name = f"{curriculum.university} {curriculum.regulation}" if curriculum.curriculum_type == "university" else "PCI Master"
            results.append({
                "id": curriculum.id,
                "university": curriculum.university,
                "regulation": curriculum.regulation,
                "course": curriculum.course,
                "effective_year": curriculum.effective_year,
                "curriculum_type": curriculum.curriculum_type,
                "curriculum_data": curriculum.curriculum_data,
                "stats": curriculum.stats,
                "status": curriculum.status,
                "created_at": curriculum.created_at.isoformat() if curriculum.created_at else "",
                "updated_at": curriculum.updated_at.isoformat() if curriculum.updated_at else None,
                "display_name": display_name
            })
        
        return {"curricula": results}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get curricula: {str(e)}"
        )

class TopicMappingResponse(BaseModel):
    id: int
    topic_slug: str
    pci_topic: str
    pci_subject_code: Optional[str] = None
    pci_unit_number: Optional[int] = None
    pci_unit_title: Optional[str] = None
    university_topic: str
    university_subject_code: str
    university_unit_number: int
    university_name: Optional[str] = None
    regulation: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@router.get("/api/curriculum/topic-mappings", response_model=List[TopicMappingResponse])
async def get_topic_mappings(
    university_name: Optional[str] = Query(None, description="Filter by university name"),
    university_subject_code: Optional[str] = Query(None, description="Filter by university subject code"),
    db: Session = Depends(get_db),
):
    """
    Get saved topic mappings from database.
    Can filter by university_name and/or university_subject_code.
    """
    try:
        query = db.query(TopicMapping)
        
        if university_name:
            query = query.filter(TopicMapping.university_name == university_name)
        
        if university_subject_code:
            query = query.filter(TopicMapping.university_subject_code == university_subject_code)
        
        mappings = query.all()
        
        return [
            TopicMappingResponse(
                id=m.id,
                topic_slug=m.topic_slug,
                pci_topic=m.pci_topic,
                pci_subject_code=m.pci_subject_code,
                pci_unit_number=m.pci_unit_number,
                pci_unit_title=m.pci_unit_title,
                university_topic=m.university_topic,
                university_subject_code=m.university_subject_code,
                university_unit_number=m.university_unit_number,
                university_name=m.university_name,
                regulation=m.regulation,
                created_at=m.created_at.isoformat() if m.created_at else None,
                updated_at=m.updated_at.isoformat() if m.updated_at else None,
            )
            for m in mappings
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch topic mappings: {str(e)}"
        )

@router.get("/api/curriculum/{curriculum_id}", response_model=Dict[str, Any])
async def get_curriculum(
    curriculum_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific curriculum by ID"""
    try:
        curriculum = db.query(UniversityCurriculum).filter(
            UniversityCurriculum.id == curriculum_id
        ).first()
        
        if not curriculum:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Curriculum not found"
            )
        
        return {
            "id": curriculum.id,
            "university": curriculum.university,
            "regulation": curriculum.regulation,
            "course": curriculum.course,
            "effective_year": curriculum.effective_year,
            "curriculum_type": curriculum.curriculum_type,
            "curriculum_data": curriculum.curriculum_data,
            "stats": curriculum.stats,
            "status": curriculum.status,
            "created_at": curriculum.created_at.isoformat() if curriculum.created_at else None,
            "updated_at": curriculum.updated_at.isoformat() if curriculum.updated_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get curriculum: {str(e)}"
        )

@router.put("/api/curriculum/{curriculum_id}", response_model=CurriculumResponse)
async def update_curriculum(
    curriculum_id: int,
    request: CurriculumCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update an existing curriculum"""
    try:
        curriculum = db.query(UniversityCurriculum).filter(
            UniversityCurriculum.id == curriculum_id
        ).first()
        
        if not curriculum:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Curriculum not found"
            )
        
        # Normalize curriculum data
        data_dict = request.curriculum_data.model_dump()
        normalized = normalize_curriculum_data(data_dict)
        
        # Calculate stats
        stats = calculate_stats(normalized)
        
        # Update curriculum
        curriculum.curriculum_data = normalized
        curriculum.stats = stats
        curriculum.updated_at = datetime.now()
        
        if request.university:
            curriculum.university = request.university
        if request.regulation:
            curriculum.regulation = request.regulation
        if request.effective_year:
            curriculum.effective_year = request.effective_year
        
        db.commit()
        db.refresh(curriculum)
        
        # Update JSON file
        save_curriculum_to_file(str(curriculum.id), {
            "id": curriculum.id,
            "university": curriculum.university,
            "regulation": curriculum.regulation,
            "course": curriculum.course,
            "effective_year": curriculum.effective_year,
            "curriculum_type": curriculum.curriculum_type,
            "curriculum_data": normalized,
            "stats": stats,
            "status": curriculum.status,
            "created_at": curriculum.created_at.isoformat() if curriculum.created_at else None,
            "updated_at": curriculum.updated_at.isoformat() if curriculum.updated_at else None,
        })
        
        display_name = f"{curriculum.university} {curriculum.regulation}" if curriculum.curriculum_type == "university" else "PCI Master"
        
        return CurriculumResponse(
            id=curriculum.id,
            university=curriculum.university,
            regulation=curriculum.regulation,
            course=curriculum.course,
            effective_year=curriculum.effective_year,
            curriculum_type=curriculum.curriculum_type,
            stats=curriculum.stats,
            status=curriculum.status,
            created_at=curriculum.created_at.isoformat() if curriculum.created_at else "",
            updated_at=curriculum.updated_at.isoformat() if curriculum.updated_at else None,
            display_name=display_name
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update curriculum: {str(e)}"
        )

def update_curricula_index(curriculum_id: str, curriculum: UniversityCurriculum):
    """Update the curricula index file"""
    index_file = os.path.join(DATA_DIR, "curricula_index.json")
    
    try:
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                index = json.load(f)
        else:
            index = []
        
        # Remove existing entry if present
        index = [c for c in index if c.get("id") != curriculum_id]
        
        # Add new entry
        display_name = f"{curriculum.university} {curriculum.regulation}" if curriculum.curriculum_type == "university" else "PCI Master"
        index.append({
            "id": curriculum_id,
            "display_name": display_name,
            "university": curriculum.university,
            "regulation": curriculum.regulation,
            "course": curriculum.course,
            "curriculum_type": curriculum.curriculum_type,
            "status": curriculum.status,
            "created_at": curriculum.created_at.isoformat() if curriculum.created_at else None,
        })
        
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error updating curricula index: {e}")

# Topic Mapping Models and Endpoints
class TopicMappingItem(BaseModel):
    university_topic: str
    university_unit_number: int
    pci_topic: str
    pci_subject_code: Optional[str] = None
    pci_unit_number: Optional[int] = None
    pci_unit_title: Optional[str] = None

class TopicMappingSaveRequest(BaseModel):
    university_name: str
    regulation: Optional[str] = None
    university_subject_code: str
    topic_mappings: List[TopicMappingItem]

class TopicMappingSaveResponse(BaseModel):
    success: bool
    saved_count: int
    message: str

@router.post("/api/curriculum/topic-mappings", response_model=TopicMappingSaveResponse)
async def save_topic_mappings(
    request: TopicMappingSaveRequest,
    db: Session = Depends(get_db),
    # current_user = Depends(get_current_user)  # Uncomment when auth is needed
):
    """
    Save topic mappings from university curriculum to PCI topics.
    Generates topic slugs that match the content_library format.
    """
    # Validate request
    if not request.topic_mappings or len(request.topic_mappings) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No topic mappings provided"
        )
    
    if not request.university_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="university_name is required"
        )
    
    if not request.university_subject_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="university_subject_code is required"
        )
    
    try:
        saved_count = 0
        errors = []
        skipped_count = 0
        
        # Track processed mappings to avoid duplicates within the same batch
        processed_keys = set()
        
        for mapping in request.topic_mappings:
            try:
                # Generate topic slug from PCI topic name with unit context
                # IMPORTANT: This uses the same generate_topic_slug() function as content_library
                # to ensure slugs match between topic_mappings and content_library tables.
                # Unit and subject information are included to ensure uniqueness when the same
                # topic name exists in different units.
                # This allows linking uploaded documents/videos (content_library) to mapped topics (topic_mappings).
                # Example: 
                #   - "Structure of Cell" in Unit 1 -> "bp101t-unit-1-structure-of-cell"
                #   - "Structure of Cell" in Unit 2 -> "bp101t-unit-2-structure-of-cell"
                topic_slug = generate_topic_slug(
                    mapping.pci_topic,
                    unit_number=mapping.pci_unit_number,
                    subject_code=mapping.pci_subject_code
                )
                
                if not topic_slug:
                    errors.append(f"Failed to generate slug for topic: {mapping.pci_topic}")
                    continue
                
                # Create a unique key for this specific mapping
                mapping_key = f"{request.university_subject_code}_{mapping.university_unit_number}_{mapping.university_topic}"
                
                # Check if we've already processed this exact mapping in this batch
                if mapping_key in processed_keys:
                    skipped_count += 1
                    continue
                processed_keys.add(mapping_key)
                
                # Check if mapping already exists in database by university topic
                existing = db.query(TopicMapping).filter(
                    and_(
                        TopicMapping.university_subject_code == request.university_subject_code,
                        TopicMapping.university_unit_number == mapping.university_unit_number,
                        TopicMapping.university_topic == mapping.university_topic
                    )
                ).first()
                
                if existing:
                    # Update existing mapping
                    existing.topic_slug = topic_slug
                    existing.pci_topic = mapping.pci_topic
                    existing.pci_subject_code = mapping.pci_subject_code
                    existing.pci_unit_number = mapping.pci_unit_number
                    existing.pci_unit_title = mapping.pci_unit_title
                    existing.university_name = request.university_name
                    existing.regulation = request.regulation
                    existing.updated_at = datetime.now()
                    db.commit()
                    saved_count += 1
                else:
                    # Check if topic_slug already exists (due to unique constraint)
                    # This can happen if multiple university topics map to the same PCI topic
                    slug_exists = db.query(TopicMapping).filter(
                        TopicMapping.topic_slug == topic_slug
                    ).first()
                    
                    if slug_exists:
                        # If unique constraint still exists, we need to handle this
                        # Try to insert, but catch the unique violation
                        try:
                            topic_mapping = TopicMapping(
                                topic_slug=topic_slug,
                                pci_topic=mapping.pci_topic,
                                pci_subject_code=mapping.pci_subject_code,
                                pci_unit_number=mapping.pci_unit_number,
                                pci_unit_title=mapping.pci_unit_title,
                                university_topic=mapping.university_topic,
                                university_subject_code=request.university_subject_code,
                                university_unit_number=mapping.university_unit_number,
                                university_name=request.university_name,
                                regulation=request.regulation
                            )
                            db.add(topic_mapping)
                            db.commit()
                            saved_count += 1
                        except Exception as db_error:
                            db.rollback()
                            # Check if it's a unique constraint violation on topic_slug
                            if "topic_slug" in str(db_error) or "UniqueViolation" in str(type(db_error).__name__):
                                # This means the unique constraint still exists - skip this record
                                errors.append(f"Skipped {mapping.university_topic}: topic_slug '{topic_slug}' already exists (unique constraint). Please run migration to remove unique constraint on topic_slug.")
                                skipped_count += 1
                            else:
                                raise
                    else:
                        # No conflict, safe to insert
                        topic_mapping = TopicMapping(
                            topic_slug=topic_slug,
                            pci_topic=mapping.pci_topic,
                            pci_subject_code=mapping.pci_subject_code,
                            pci_unit_number=mapping.pci_unit_number,
                            pci_unit_title=mapping.pci_unit_title,
                            university_topic=mapping.university_topic,
                            university_subject_code=request.university_subject_code,
                            university_unit_number=mapping.university_unit_number,
                            university_name=request.university_name,
                            regulation=request.regulation
                        )
                        db.add(topic_mapping)
                        db.commit()
                        saved_count += 1
                
            except Exception as e:
                db.rollback()
                errors.append(f"Error saving mapping for {mapping.university_topic}: {str(e)}")
                continue
        
        message = f"Successfully saved {saved_count} topic mapping(s)"
        if skipped_count > 0:
            message += f". {skipped_count} skipped (duplicates or constraint violations)."
        if errors:
            message += f" {len(errors)} error(s) occurred."
        
        return TopicMappingSaveResponse(
            success=True,
            saved_count=saved_count,
            message=message
        )
        
    except Exception as e:
        db.rollback()
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Failed to save topic mappings: {str(e)}")
        print(f"[ERROR] Traceback: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save topic mappings: {str(e)}"
        )
        