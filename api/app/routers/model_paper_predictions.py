import os
import json
import logging
import re
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
import openai
from openai import OpenAI
import google.generativeai as genai
from sqlalchemy.orm import Session
from ..core.security import get_current_user
from ..core.dual_auth import get_dual_auth_user
from ..config.settings import (
    OPENAI_API_KEY,
    GOOGLE_API_KEY,
    AI_PROVIDER,
    CHAT_MODEL,
    OPENAI_FALLBACK_MODEL
)
from ..config.database import get_db
from ..utils.file_utils import extract_text_from_pdf, extract_text_from_docx_python_docx
from ..utils.s3_utils import get_file_from_s3
from ..services.prediction_service import PredictionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/model_paper_predictions.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/model-paper-predictions",
    tags=["model-paper-predictions"]
)

# Constants
PREDICTIONS_METADATA_KEY = "metadata/model_paper_predictions.json"
REQUIRED_SECTION_KEYWORDS = [
    "Comprehensive Questions",
    "Focused Questions",
    "Quick Assessment Questions"
]
MIN_QUESTIONS_PER_SECTION = 3

def save_predictions_metadata(predictions: list) -> bool:
    """Save predictions metadata to S3"""
    try:
        import boto3
        from ..config.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        json_data = json.dumps(predictions, indent=2)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=PREDICTIONS_METADATA_KEY,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except Exception as e:
        logger.error(f"Failed to save predictions metadata: {str(e)}")
        return False

def load_predictions_metadata() -> list:
    """Load predictions metadata from S3"""
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
            Key=PREDICTIONS_METADATA_KEY
        )
        json_data = response['Body'].read().decode('utf-8')
        return json.loads(json_data)
    except Exception as e:
        if "NoSuchKey" in str(e):
            return []
        logger.error(f"Failed to load predictions metadata: {str(e)}")
        return []

def extract_text_from_model_paper(s3_key: str, content_type: str) -> str:
    """Extract text from model paper file stored in S3"""
    try:
        # Get file from S3
        file_content = get_file_from_s3(s3_key)
        
        if not file_content:
            raise Exception("Failed to retrieve file from S3")
        
        # Create temporary file for processing
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(s3_key)[1]) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        try:
            # Extract text based on file type
            if content_type == 'application/pdf':
                text = extract_text_from_pdf(temp_file_path)
            elif content_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
                text = extract_text_from_docx_python_docx(temp_file_path)
            else:
                # Try to decode as text
                text = file_content.decode('utf-8', errors='ignore')
            
            return text.strip()
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        logger.error(f"Failed to extract text from model paper: {str(e)}")
        raise

def predict_questions_with_openai(model_paper_text: str) -> str:
    """Use AI to predict questions from model paper text"""
    try:
        # Load the template from AI router
        from .ai import load_model_paper_prediction_template
        template = load_model_paper_prediction_template()
        
        if not template:
            raise Exception("Prompt failed to load")
        
        # Prepare the prompt using the template
        prompt = template.format(
            model_paper_content=model_paper_text,
            model_paper_text=model_paper_text
        )
        
        # Make AI request
        return _make_ai_request(prompt)
        
    except Exception as e:
        logger.error(f"Failed to predict questions: {str(e)}")
        raise Exception(f"Prompt failed to load: {str(e)}")

def _make_ai_request(prompt: str) -> str:
    """Make AI request with validation and retry handling"""

    response = _invoke_ai_provider(prompt)
    is_valid, reason = _validate_prediction_output(response)
    if is_valid:
        return response

    logger.warning(f"AI response missing required structure ({reason}). Retrying with reinforcement.")
    reinforced_prompt = (
        f"{prompt}\n\nREMINDER: Include all three sections (Comprehensive, Focused, Quick Assessment) with numbered questions and end with the line 'DONE'."
    )
    response = _invoke_ai_provider(reinforced_prompt)
    is_valid, reason = _validate_prediction_output(response)
    if is_valid:
        return response

    logger.error(f"AI response still invalid after retry: {reason}")
    raise Exception(f"AI response incomplete: {reason}")


def _invoke_ai_provider(prompt: str) -> str:
    """Call the configured AI provider, falling back to OpenAI when needed."""

    if AI_PROVIDER == "google" and GOOGLE_API_KEY:
        try:
            logger.info("Attempting Google AI request")
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel(CHAT_MODEL)

            response = model.generate_content(
                f"You are an educational content specialist focused on creating learning materials.\n\n{prompt}",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=2000,
                    temperature=0.7
                )
            )

            if not response.candidates or not response.candidates[0].content.parts:
                finish_reason = response.candidates[0].finish_reason if response.candidates else "No candidates"
                logger.error(f"Google API response blocked or empty. Finish reason: {finish_reason}")
                raise Exception("Content generation was blocked or returned empty output")

            predicted_questions = response.text.strip()
            logger.info("Google AI request successful")
            return predicted_questions

        except Exception as e:
            logger.warning(f"Google AI request failed: {str(e)}")
            if OPENAI_API_KEY:
                logger.info("Attempting fallback to OpenAI provider")
                return _make_openai_request(prompt, model_name=OPENAI_FALLBACK_MODEL)
            raise

    return _make_openai_request(prompt, model_name=OPENAI_FALLBACK_MODEL)

def _make_openai_request(prompt: str, model_name: Optional[str] = None) -> str:
    """Make OpenAI request"""
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not configured")
    
    model_to_use = model_name or OPENAI_FALLBACK_MODEL
    logger.info(f"Making OpenAI request using model: {model_to_use}")
    # Configure OpenAI client for v1.0.0+
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # Make API call to OpenAI
    response = client.chat.completions.create(
        model=model_to_use,
        messages=[
            {
                "role": "system",
                "content": "You are an educational content specialist focused on creating learning materials."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=2000,
        temperature=0.7
    )
    
    # Extract the response
    predicted_questions = response.choices[0].message.content.strip()
    logger.info("OpenAI request successful")
    return predicted_questions


def _validate_prediction_output(output: str) -> (bool, str):
    """Ensure the AI response contains all required sections and the DONE marker."""
    if not output or not output.strip():
        return False, "Empty response"

    trimmed_output = output.strip()
    if not trimmed_output.endswith("DONE"):
        return False, "Missing terminating DONE line"

    sections = _extract_sections(output)

    for keyword in REQUIRED_SECTION_KEYWORDS:
        matching_heading = _find_section_heading(sections, keyword)
        if not matching_heading:
            return False, f"Missing section for '{keyword}'"

        question_lines = [
            line for line in sections[matching_heading]
            if re.match(r"^\s*\d+\.\s+", line)
        ]

        if len(question_lines) < MIN_QUESTIONS_PER_SECTION:
            return False, f"Not enough questions in section '{keyword}'"

    return True, ""


def _extract_sections(output: str) -> Dict[str, List[str]]:
    """Parse markdown-style sections into a dictionary of heading -> lines."""
    sections: Dict[str, List[str]] = {}
    current_heading: Optional[str] = None

    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            current_heading = stripped
            sections[current_heading] = []
            continue

        if current_heading is not None:
            sections[current_heading].append(line)

    return sections


def _find_section_heading(sections: Dict[str, List[str]], keyword: str) -> Optional[str]:
    """Find the section heading containing the keyword (case-insensitive)."""
    keyword_lower = keyword.lower()
    for heading in sections.keys():
        if keyword_lower in heading.lower():
            return heading
    return None

def _clean_text_for_ai(text: str) -> str:
    """Clean text to make it safer for AI processing"""
    import re
    
    # Remove excessive whitespace and normalize
    text = re.sub(r'\s+', ' ', text)
    
    # Remove any potentially problematic characters or patterns
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # Remove email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    
    # Remove excessive punctuation
    text = re.sub(r'[!]{2,}', '!', text)
    text = re.sub(r'[?]{2,}', '?', text)
    
    # Remove any content that might trigger safety filters
    # Remove any text that looks like personal information
    text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '', text)  # Remove dates
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '', text)  # Remove SSN patterns
    
    # Limit text length to avoid token limits
    max_length = 8000  # Conservative limit
    if len(text) > max_length:
        text = text[:max_length]
        logger.info(f"Text truncated to {max_length} characters")
    
    return text.strip()

async def process_model_paper_prediction(
    model_paper_id: str,
    files: List[Dict[str, Any]],
    course_name: str,
    year: str,
    semester: str,
    subject: str,
    user_id: str
):
    """Background task to process model paper and generate predictions"""
    db = next(get_db())
    prediction_id = None
    
    try:
        logger.info(f"Starting prediction processing for model paper: {model_paper_id} with {len(files)} files")
        
        # Create prediction record in database
        prediction = PredictionService.create_prediction(
            db=db,
            model_paper_id=model_paper_id,
            course_name=course_name,
            year=year,
            academic_year=year,
            semester=semester,
            subject=subject,
            processed_by=user_id,
            s3_key=f"multiple_files_{len(files)}"  # Store count instead of single key
        )
        prediction_id = prediction.id
        
        # Extract text from all model paper files
        all_text_content = []
        total_text_length = 0
        
        for file_info in files:
            try:
                s3_key = file_info["s3_key"]
                content_type = file_info["content_type"]
                filename = file_info["filename"]
                
                logger.info(f"Processing file: {filename}")
                
                # Extract text from this file
                file_text = extract_text_from_model_paper(s3_key, content_type)
                
                if file_text:
                    # Add file header to distinguish content
                    file_content = f"\n\n--- Content from {filename} ---\n\n{file_text}"
                    all_text_content.append(file_content)
                    total_text_length += len(file_text)
                    logger.info(f"Extracted {len(file_text)} characters from {filename}")
                else:
                    logger.warning(f"No text extracted from {filename}")
                    
            except Exception as file_error:
                logger.error(f"Failed to process file {file_info.get('filename', 'unknown')}: {str(file_error)}")
                continue
        
        if not all_text_content:
            raise Exception("No text extracted from any model paper files")
        
        # Combine all text content
        combined_text = "\n".join(all_text_content)
        logger.info(f"Combined text from {len(files)} files: {total_text_length} characters")
        
        # Log first 500 characters for debugging
        logger.info(f"First 500 characters of combined text: {combined_text[:500]}")
        
        # Clean and prepare text for AI processing
        cleaned_text = _clean_text_for_ai(combined_text)
        logger.info(f"Cleaned text length: {len(cleaned_text)} characters")
        
        # Predict questions using AI
        predicted_questions = predict_questions_with_openai(cleaned_text)
        
        # Update prediction with results
        PredictionService.update_prediction_status(
            db=db,
            prediction_id=prediction_id,
            status='completed',
            predicted_questions=predicted_questions,
            text_length=total_text_length
        )
        
        # Also save to S3 for backup
        prediction_data = {
            "id": prediction_id,
            "model_paper_id": model_paper_id,
            "course_name": course_name,
            "year": year,
            "academic_year": year,
            "semester": semester,
            "subject": subject,
            "predicted_questions": predicted_questions,
            "text_length": total_text_length,
            "processed_by": user_id,
            "processed_at": datetime.now().isoformat(),
            "status": "completed",
            "files_processed": len(files),
            "file_details": [{"filename": f["filename"], "size": f["file_size"]} for f in files]
        }
        
        predictions = load_predictions_metadata()
        predictions.append(prediction_data)
        save_predictions_metadata(predictions)
        
        logger.info(f"Successfully processed prediction for model paper: {model_paper_id}")
        
    except Exception as e:
        logger.error(f"Failed to process prediction for model paper {model_paper_id}: {str(e)}")
        
        # Update prediction status to failed
        if prediction_id:
            PredictionService.update_prediction_status(
                db=db,
                prediction_id=prediction_id,
                status='failed',
                error_message=str(e)
            )
        
        # Also save failed prediction to S3
        failed_prediction = {
            "id": prediction_id or str(uuid.uuid4()),
            "model_paper_id": model_paper_id,
            "course_name": course_name,
            "year": year,
            "academic_year": year,
            "semester": semester,
            "subject": subject,
            "predicted_questions": "",
            "text_length": 0,
            "processed_by": user_id,
            "processed_at": datetime.now().isoformat(),
            "status": "failed",
            "error": str(e),
            "files_processed": len(files) if files else 0
        }
        
        predictions = load_predictions_metadata()
        predictions.append(failed_prediction)
        save_predictions_metadata(predictions)
    
    finally:
        db.close()

@router.post("/predict/{model_paper_id}")
async def predict_questions_from_model_paper(
    model_paper_id: str,
    background_tasks: BackgroundTasks,
    auth_result: dict = Depends(get_dual_auth_user)
):
    """Start prediction process for a model paper"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting prediction for model paper: {model_paper_id}")
        
        # Load model papers metadata to get the paper details
        from .model_papers import load_model_papers_metadata
        from ..config.database import get_db
        
        model_papers = load_model_papers_metadata()
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
        
        # Check if prediction already exists in database
        db = next(get_db())
        try:
            existing_prediction = PredictionService.get_prediction_by_model_paper_id(
                db=db, 
                model_paper_id=model_paper_id
            )
            
            if existing_prediction:
                return {
                    "message": "Prediction already exists for this model paper",
                    "prediction_id": existing_prediction.id,
                    "status": existing_prediction.status
                }
        finally:
            db.close()
        
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
        
        # Start background processing
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
        
        return {
            "message": "Prediction process started",
            "model_paper_id": model_paper_id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting prediction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start prediction: {str(e)}"
        )

@router.get("/predictions")
async def get_predictions(
    model_paper_id: Optional[str] = None,
    course_name: Optional[str] = None,
    subject: Optional[str] = None,
    status: Optional[str] = None,
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """Get predictions with optional filtering"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting predictions")
        
        # Get predictions from database
        predictions = PredictionService.get_predictions(
            db=db,
            model_paper_id=model_paper_id,
            course_name=course_name,
            subject=subject,
            status=status
        )
        
        # Convert to dict format for API response
        prediction_list = []
        for pred in predictions:
            prediction_dict = {
                "id": pred.id,
                "model_paper_id": pred.model_paper_id,
                "course_name": pred.course_name,
                "year": pred.year,
                "academic_year": getattr(pred, "academic_year", None),
                "semester": pred.semester,
                "subject": pred.subject,
                "predicted_questions": pred.predicted_questions,
                "text_length": pred.text_length,
                "processed_by": pred.processed_by,
                "status": pred.status,
                "error": pred.error_message,
                "processed_at": pred.created_at.isoformat() if pred.created_at else None,
                "updated_at": pred.updated_at.isoformat() if pred.updated_at else None
            }
            prediction_list.append(prediction_dict)
        
        total_count = PredictionService.count_predictions(
            db=db,
            model_paper_id=model_paper_id,
            course_name=course_name,
            subject=subject,
            status=status
        )
        
        logger.info(f"Found {len(prediction_list)} predictions matching criteria")
        
        return {
            "predictions": prediction_list,
            "total": total_count
        }
        
    except Exception as e:
        logger.error(f"Error getting predictions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get predictions: {str(e)}"
        )

@router.get("/predictions/{prediction_id}")
async def get_prediction_by_id(
    prediction_id: str,
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """Get a specific prediction by ID"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} requesting prediction: {prediction_id}")
        
        prediction = PredictionService.get_prediction_by_id(db=db, prediction_id=prediction_id)
        
        if not prediction:
            raise HTTPException(
                status_code=404,
                detail="Prediction not found"
            )
        
        # Convert to dict format for API response
        prediction_dict = {
            "id": prediction.id,
            "model_paper_id": prediction.model_paper_id,
            "course_name": prediction.course_name,
            "year": prediction.year,
            "academic_year": getattr(prediction, "academic_year", None),
            "semester": prediction.semester,
            "subject": prediction.subject,
            "predicted_questions": prediction.predicted_questions,
            "text_length": prediction.text_length,
            "processed_by": prediction.processed_by,
            "status": prediction.status,
            "error": prediction.error_message,
            "processed_at": prediction.created_at.isoformat() if prediction.created_at else None,
            "updated_at": prediction.updated_at.isoformat() if prediction.updated_at else None
        }
        
        return prediction_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prediction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get prediction: {str(e)}"
        )

@router.delete("/predictions/{prediction_id}")
async def delete_prediction(
    prediction_id: str,
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db)
):
    """Delete a prediction"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} deleting prediction: {prediction_id}")
        
        # Delete from database
        success = PredictionService.delete_prediction(db=db, prediction_id=prediction_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Prediction not found"
            )
        
        # Also remove from S3 backup
        predictions = load_predictions_metadata()
        predictions = [p for p in predictions if p.get('id') != prediction_id]
        save_predictions_metadata(predictions)
        
        logger.info(f"Prediction deleted successfully: {prediction_id}")
        
        return {"message": "Prediction deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting prediction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete prediction: {str(e)}"
        )

@router.post("/predictions/{prediction_id}/retry")
async def retry_prediction(
    prediction_id: str,
    background_tasks: BackgroundTasks,
    auth_result: dict = Depends(get_dual_auth_user)
):
    """Retry a failed prediction"""
    try:
        user_id = auth_result.get('user_data', {}).get('sub', 'unknown')
        logger.info(f"User {user_id} retrying prediction: {prediction_id}")
        
        predictions = load_predictions_metadata()
        
        # Find the prediction
        prediction = next(
            (p for p in predictions if p.get('id') == prediction_id), 
            None
        )
        
        if not prediction:
            raise HTTPException(
                status_code=404,
                detail="Prediction not found"
            )
        
        if prediction.get('status') != 'failed':
            raise HTTPException(
                status_code=400,
                detail="Only failed predictions can be retried"
            )
        
        # Load model paper details
        from .model_papers import load_model_papers_metadata
        
        model_papers = load_model_papers_metadata()
        model_paper = next(
            (p for p in model_papers if p.get('id') == prediction.get('model_paper_id')), 
            None
        )
        
        if not model_paper:
            raise HTTPException(
                status_code=404,
                detail="Associated model paper not found"
            )
        
        # Update prediction status
        prediction['status'] = 'processing'
        prediction['processed_at'] = datetime.now().isoformat()
        prediction['error'] = None

        save_predictions_metadata(predictions)

        # Prepare files list for processing – support both new multi-file and legacy single-file structures
        if 'files' in model_paper:
            files = model_paper['files']
            logger.info(
                "Retrying prediction for model paper %s with %d files",
                prediction['model_paper_id'],
                len(files),
            )
        else:
            files = [
                {
                    "filename": model_paper.get('filename', 'unknown'),
                    "s3_key": model_paper.get('s3_key', ''),
                    "content_type": model_paper.get('content_type', 'application/pdf'),
                    "file_size": model_paper.get('file_size', 0),
                }
            ]
            logger.info(
                "Retrying prediction for legacy single-file model paper %s",
                prediction['model_paper_id'],
            )

        # Start background processing with the consolidated files list
        background_tasks.add_task(
            process_model_paper_prediction,
            model_paper_id=prediction['model_paper_id'],
            files=files,
            course_name=model_paper['courseName'],
            year=model_paper['year'],
            semester=model_paper['semester'],
            subject=model_paper['subject'],
            user_id=user_id,
        )

        return {
            "message": "Prediction retry started",
            "prediction_id": prediction_id,
            "status": "processing",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying prediction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retry prediction: {str(e)}"
        ) 