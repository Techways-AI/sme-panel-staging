import os
import uuid
import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from ..core.security import get_current_user
from ..core.dual_auth import get_dual_auth_user
from ..utils.s3_utils import (
    upload_file_to_s3, get_file_url, file_exists_in_s3,
    delete_file_from_s3, list_files_in_folder
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/model_papers.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/model-papers",
    tags=["model-papers"]
)

# Constants for model papers
MODEL_PAPERS_PREFIX = "model-papers/"
MODEL_PAPERS_METADATA_KEY = "metadata/model_papers.json"
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc'}

def save_model_papers_metadata(model_papers: list) -> bool:
    """Save model papers metadata to S3"""
    try:
        import boto3
        from ..config.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        json_data = json.dumps(model_papers, indent=2)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=MODEL_PAPERS_METADATA_KEY,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except Exception as e:
        logger.error(f"Failed to save model papers metadata: {str(e)}")
        return False

def load_model_papers_metadata() -> list:
    """Load model papers metadata from S3"""
    try:
        import boto3
        from ..config.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=MODEL_PAPERS_METADATA_KEY
        )
        json_data = response['Body'].read().decode('utf-8')
        return json.loads(json_data)
    except Exception as e:
        if "NoSuchKey" in str(e):
            return []
        logger.error(f"Failed to load model papers metadata: {str(e)}")
        return []

@router.get("")
async def get_model_papers(auth_result: dict = Depends(get_dual_auth_user)):
    """Get all model papers"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting model papers")
        
        model_papers = load_model_papers_metadata()
        logger.info(f"Found {len(model_papers)} model papers for user {user_id}")
        
        return {
            "model_papers": model_papers,
            "user": {
                "id": user_id,
                "permissions": auth_result.get('user_data', {}).get('permissions', [])
            }
        }
    except Exception as e:
        logger.error(f"Error getting model papers: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model papers: {str(e)}"
        )

@router.post("/upload")
async def upload_model_paper(
    background_tasks: BackgroundTasks,
    auth_result: dict = Depends(get_dual_auth_user),
    files: List[UploadFile] = File(...),
    courseName: str = Form(...),
    year: str = Form(...),
    yearName: Optional[str] = Form(None),
    semester: str = Form(...),
    subject: str = Form(...),
    description: Optional[str] = Form(None)
):
    """Upload multiple model paper documents to S3"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} uploading {len(files)} model paper files")
        
        # Validate required fields
        if not all([courseName, year, semester, subject]):
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: courseName, year, semester, subject"
            )
        
        # Validate files
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Generate unique ID for the model paper set
        model_paper_id = str(uuid.uuid4())
        
        # Process each file
        uploaded_files = []
        failed_files = []
        
        for file in files:
            try:
                # Validate file
                if not file.filename:
                    failed_files.append({"filename": "unknown", "error": "No filename provided"})
                    continue
                
                # Check file extension
                file_ext = os.path.splitext(file.filename)[1].lower()
                if file_ext not in ALLOWED_EXTENSIONS:
                    failed_files.append({"filename": file.filename, "error": f"Invalid file type: {file_ext}"})
                    continue
                
                # Check if file is empty
                content = await file.read()
                if not content:
                    failed_files.append({"filename": file.filename, "error": "Empty file provided"})
                    continue
                await file.seek(0)  # Reset file pointer
                
                # Create S3 key for this specific file
                sanitized_course = courseName.replace(' ', '_').replace('/', '_')
                sanitized_subject = subject.replace(' ', '_').replace('/', '_')
                sanitized_filename = file.filename.replace(' ', '_').replace('/', '_')
                s3_key = f"{MODEL_PAPERS_PREFIX}{sanitized_course}/{year}/{semester}/{sanitized_subject}/{model_paper_id}/{sanitized_filename}"
                
                # Check if file already exists
                if file_exists_in_s3(s3_key):
                    failed_files.append({"filename": file.filename, "error": "File already exists"})
                    continue
                
                # Upload file to S3
                file_url = upload_file_to_s3(file.file, s3_key, file.content_type)
                
                # Store file information
                file_info = {
                    "filename": file.filename,
                    "original_filename": file.filename,
                    "file_url": file_url,
                    "s3_key": s3_key,
                    "file_size": len(content),
                    "content_type": file.content_type,
                    "uploaded_at": datetime.now().isoformat()
                }
                uploaded_files.append(file_info)
                
                logger.info(f"Successfully uploaded file: {file.filename}")
                
            except Exception as e:
                logger.error(f"Failed to upload file {file.filename}: {str(e)}")
                failed_files.append({"filename": file.filename, "error": str(e)})
        
        # If no files were uploaded successfully, return error
        if not uploaded_files:
            raise HTTPException(
                status_code=400,
                detail="No files were uploaded successfully",
                headers={"X-Failed-Files": json.dumps(failed_files)}
            )
        
        # Create model paper metadata
        model_paper = {
            "id": model_paper_id,
            "courseName": courseName,
            "year": year,
            "yearName": yearName or "",
            "semester": semester,
            "subject": subject,
            "description": description or "",
            "files": uploaded_files,
            "total_files": len(uploaded_files),
            "total_size": sum(f["file_size"] for f in uploaded_files),
            "uploaded_by": user_id,
            "uploaded_at": datetime.now().isoformat(),
            "year_semester": f"{year}-{semester}",
            "failed_files": failed_files if failed_files else []
        }
        
        # Load existing model papers and add new one
        model_papers = load_model_papers_metadata()
        model_papers.append(model_paper)
        
        # Save updated metadata
        if not save_model_papers_metadata(model_papers):
            # If metadata save fails, delete all uploaded files
            for file_info in uploaded_files:
                try:
                    delete_file_from_s3(file_info["s3_key"])
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup file {file_info['filename']}: {str(cleanup_error)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to save model paper metadata"
            )
        
        logger.info(f"Model paper set uploaded successfully: {model_paper_id} with {len(uploaded_files)} files")
        
        return {
            "message": f"Model paper set uploaded successfully with {len(uploaded_files)} files",
            "model_paper": model_paper,
            "uploaded_files": len(uploaded_files),
            "failed_files": len(failed_files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading model paper: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload model paper: {str(e)}"
        )

@router.post("/{model_paper_id}/generate-prediction")
async def generate_prediction(
    model_paper_id: str,
    background_tasks: BackgroundTasks,
    auth_result: dict = Depends(get_dual_auth_user)
):
    """Manually generate prediction for a model paper"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting prediction generation for model paper: {model_paper_id}")
        
        # Load model papers
        model_papers = load_model_papers_metadata()
        
        # Find the model paper
        model_paper = None
        for paper in model_papers:
            if paper.get('id') == model_paper_id:
                model_paper = paper
                break
        
        if not model_paper:
            raise HTTPException(
                status_code=404,
                detail="Model paper not found"
            )
        
        # Check if prediction already exists
        try:
            from ..services.prediction_service import PredictionService
            from ..config.database import get_db
            
            db = next(get_db())
            try:
                existing_prediction = PredictionService.get_prediction_by_model_paper_id(
                    db=db, 
                    model_paper_id=model_paper_id
                )
                
                if existing_prediction:
                    raise HTTPException(
                        status_code=409,
                        detail="Prediction already exists for this model paper"
                    )
                    
            finally:
                db.close()
                
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Failed to check existing prediction: {str(e)}")
        
        # Get files information - handle both old single file and new multiple files structure
        if 'files' in model_paper:
            # New multiple files structure
            files = model_paper['files']
            logger.info(f"Processing {len(files)} files for model paper: {model_paper_id}")
        else:
            # Legacy single file structure - convert to new format
            files = [{
                "filename": model_paper.get('filename', 'unknown'),
                "s3_key": model_paper.get('s3_key', ''),
                "content_type": model_paper.get('content_type', 'application/pdf'),
                "file_size": model_paper.get('file_size', 0)
            }]
            logger.info(f"Processing legacy single file for model paper: {model_paper_id}")
        
        # Trigger question prediction
        from .model_paper_predictions import process_model_paper_prediction
        background_tasks.add_task(
            process_model_paper_prediction,
            model_paper_id=model_paper_id,
            files=files,
            course_name=model_paper['courseName'],
            year=model_paper['year'],
            semester=model_paper['semester'],
            subject=model_paper['subject'],
            user_id=user_id
        )
        
        logger.info(f"Question prediction task queued for model paper: {model_paper_id}")
        
        return {
            "message": "Prediction generation started successfully",
            "model_paper_id": model_paper_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating prediction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate prediction: {str(e)}"
        )

@router.delete("/{model_paper_id}")
async def delete_model_paper(
    model_paper_id: str,
    auth_result: dict = Depends(get_dual_auth_user)
):
    """Delete a model paper"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} deleting model paper: {model_paper_id}")
        
        # Check if user is authenticated (optional: you can remove this check to allow all users)
        # permissions = current_user.get('permissions', [])
        # if 'admin' not in permissions:
        #     raise HTTPException(
        #         status_code=403,
        #         detail="Only admins can delete model papers"
        #     )
        
        # Load model papers
        model_papers = load_model_papers_metadata()
        
        # Find the model paper
        model_paper = None
        for paper in model_papers:
            if paper.get('id') == model_paper_id:
                model_paper = paper
                break
        
        if not model_paper:
            raise HTTPException(
                status_code=404,
                detail="Model paper not found"
            )
        
        # Delete file from S3
        try:
            delete_file_from_s3(model_paper['s3_key'])
        except Exception as e:
            logger.warning(f"Failed to delete file from S3: {str(e)}")
        
        # Delete associated prediction from database
        try:
            from ..services.prediction_service import PredictionService
            from ..config.database import get_db
            
            db = next(get_db())
            try:
                existing_prediction = PredictionService.get_prediction_by_model_paper_id(
                    db=db, 
                    model_paper_id=model_paper_id
                )
                
                if existing_prediction:
                    PredictionService.delete_prediction(db=db, prediction_id=existing_prediction.id)
                    logger.info(f"Deleted associated prediction: {existing_prediction.id}")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.warning(f"Failed to delete associated prediction: {str(e)}")
        
        # Remove from metadata
        model_papers = [paper for paper in model_papers if paper.get('id') != model_paper_id]
        
        # Save updated metadata
        if not save_model_papers_metadata(model_papers):
            raise HTTPException(
                status_code=500,
                detail="Failed to update model papers metadata"
            )
        
        logger.info(f"Model paper deleted successfully: {model_paper_id}")
        
        return {"message": "Model paper deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting model paper: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete model paper: {str(e)}"
        )

@router.get("/search")
async def search_model_papers(
    courseName: Optional[str] = None,
    year: Optional[str] = None,
    semester: Optional[str] = None,
    subject: Optional[str] = None,
    auth_result: dict = Depends(get_dual_auth_user)
):
    """Search model papers by criteria"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} searching model papers")
        
        model_papers = load_model_papers_metadata()
        
        # Filter by criteria
        filtered_papers = model_papers
        
        if courseName:
            filtered_papers = [paper for paper in filtered_papers 
                             if courseName.lower() in paper.get('courseName', '').lower()]
        
        if year:
            filtered_papers = [paper for paper in filtered_papers 
                             if paper.get('year') == year]
        
        if semester:
            filtered_papers = [paper for paper in filtered_papers 
                             if paper.get('semester') == semester]
        
        if subject:
            filtered_papers = [paper for paper in filtered_papers 
                             if subject.lower() in paper.get('subject', '').lower()]
        
        logger.info(f"Found {len(filtered_papers)} model papers matching criteria")
        
        return {
            "model_papers": filtered_papers,
            "total": len(filtered_papers)
        }
        
    except Exception as e:
        logger.error(f"Error searching model papers: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search model papers: {str(e)}"
        )

@router.get("/courses")
async def get_available_courses(auth_result: dict = Depends(get_dual_auth_user)):
    """Get list of available courses"""
    try:
        model_papers = load_model_papers_metadata()
        courses = list(set(paper.get('courseName') for paper in model_papers if paper.get('courseName')))
        return {"courses": sorted(courses)}
    except Exception as e:
        logger.error(f"Error getting courses: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get courses: {str(e)}"
        )

@router.get("/subjects")
async def get_available_subjects(
    courseName: Optional[str] = None,
    auth_result: dict = Depends(get_dual_auth_user)
):
    """Get list of available subjects"""
    try:
        model_papers = load_model_papers_metadata()
        
        if courseName:
            model_papers = [paper for paper in model_papers 
                           if paper.get('courseName') == courseName]
        
        subjects = list(set(paper.get('subject') for paper in model_papers if paper.get('subject')))
        return {"subjects": sorted(subjects)}
    except Exception as e:
        logger.error(f"Error getting subjects: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get subjects: {str(e)}"
        ) 