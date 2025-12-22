import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ..models.model_paper_prediction import ModelPaperPrediction
from ..config.database import get_db

logger = logging.getLogger(__name__)

class PredictionService:
    """Service class for handling model paper prediction database operations"""
    
    @staticmethod
    def create_prediction(
        db: Session,
        model_paper_id: str,
        course_name: str,
        year: str,
        academic_year: Optional[str],
        semester: str,
        subject: str,
        processed_by: str,
        s3_key: Optional[str] = None,
        prediction_metadata: Optional[Dict] = None
    ) -> ModelPaperPrediction:
        """Create a new prediction record"""
        try:
            prediction_id = str(uuid.uuid4())
            prediction = ModelPaperPrediction(
                id=prediction_id,
                model_paper_id=model_paper_id,
                course_name=course_name,
                year=year,
                academic_year=academic_year,
                semester=semester,
                subject=subject,
                processed_by=processed_by,
                status='processing',
                s3_key=s3_key,
                prediction_metadata=prediction_metadata
            )
            
            db.add(prediction)
            db.commit()
            db.refresh(prediction)
            
            logger.info(f"Created prediction record: {prediction_id}")
            return prediction
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create prediction: {str(e)}")
            raise
    
    @staticmethod
    def update_prediction_status(
        db: Session,
        prediction_id: str,
        status: str,
        predicted_questions: Optional[str] = None,
        text_length: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> Optional[ModelPaperPrediction]:
        """Update prediction status and results"""
        try:
            prediction = db.query(ModelPaperPrediction).filter(
                ModelPaperPrediction.id == prediction_id
            ).first()
            
            if not prediction:
                logger.warning(f"Prediction not found: {prediction_id}")
                return None
            
            prediction.status = status
            prediction.updated_at = datetime.now()
            
            if predicted_questions is not None:
                prediction.predicted_questions = predicted_questions
            
            if text_length is not None:
                prediction.text_length = text_length
            
            if error_message is not None:
                prediction.error_message = error_message
            
            db.commit()
            db.refresh(prediction)
            
            logger.info(f"Updated prediction {prediction_id} status to: {status}")
            return prediction
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update prediction {prediction_id}: {str(e)}")
            raise
    
    @staticmethod
    def get_prediction_by_id(db: Session, prediction_id: str) -> Optional[ModelPaperPrediction]:
        """Get prediction by ID"""
        try:
            return db.query(ModelPaperPrediction).filter(
                ModelPaperPrediction.id == prediction_id
            ).first()
        except Exception as e:
            logger.error(f"Failed to get prediction {prediction_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_predictions(
        db: Session,
        model_paper_id: Optional[str] = None,
        course_name: Optional[str] = None,
        subject: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ModelPaperPrediction]:
        """Get predictions with optional filtering"""
        try:
            query = db.query(ModelPaperPrediction)
            
            # Apply filters
            if model_paper_id:
                query = query.filter(ModelPaperPrediction.model_paper_id == model_paper_id)
            
            if course_name:
                query = query.filter(ModelPaperPrediction.course_name.ilike(f"%{course_name}%"))
            
            if subject:
                query = query.filter(ModelPaperPrediction.subject.ilike(f"%{subject}%"))
            
            if status:
                query = query.filter(ModelPaperPrediction.status == status)
            
            # Order by creation date (newest first)
            query = query.order_by(ModelPaperPrediction.created_at.desc())
            
            # Apply pagination
            query = query.offset(offset).limit(limit)
            
            return query.all()
            
        except Exception as e:
            logger.error(f"Failed to get predictions: {str(e)}")
            return []
    
    @staticmethod
    def get_prediction_by_model_paper_id(db: Session, model_paper_id: str) -> Optional[ModelPaperPrediction]:
        """Get prediction by model paper ID"""
        try:
            return db.query(ModelPaperPrediction).filter(
                ModelPaperPrediction.model_paper_id == model_paper_id
            ).first()
        except Exception as e:
            logger.error(f"Failed to get prediction for model paper {model_paper_id}: {str(e)}")
            return None
    
    @staticmethod
    def delete_prediction(db: Session, prediction_id: str) -> bool:
        """Delete a prediction"""
        try:
            prediction = db.query(ModelPaperPrediction).filter(
                ModelPaperPrediction.id == prediction_id
            ).first()
            
            if not prediction:
                logger.warning(f"Prediction not found for deletion: {prediction_id}")
                return False
            
            db.delete(prediction)
            db.commit()
            
            logger.info(f"Deleted prediction: {prediction_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete prediction {prediction_id}: {str(e)}")
            return False
    
    @staticmethod
    def count_predictions(
        db: Session,
        model_paper_id: Optional[str] = None,
        course_name: Optional[str] = None,
        subject: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """Count predictions with optional filtering"""
        try:
            query = db.query(ModelPaperPrediction)
            
            # Apply filters
            if model_paper_id:
                query = query.filter(ModelPaperPrediction.model_paper_id == model_paper_id)
            
            if course_name:
                query = query.filter(ModelPaperPrediction.course_name.ilike(f"%{course_name}%"))
            
            if subject:
                query = query.filter(ModelPaperPrediction.subject.ilike(f"%{subject}%"))
            
            if status:
                query = query.filter(ModelPaperPrediction.status == status)
            
            return query.count()
            
        except Exception as e:
            logger.error(f"Failed to count predictions: {str(e)}")
            return 0 