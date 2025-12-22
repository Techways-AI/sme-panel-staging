from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Boolean
from sqlalchemy.sql import func
from ..config.database import Base

class ModelPaperPrediction(Base):
    __tablename__ = "model_paper_predictions"

    id = Column(String, primary_key=True, index=True)  # prediction_id
    model_paper_id = Column(String, nullable=False, index=True)  # Reference to model paper
    course_name = Column(String, nullable=False, index=True)
    year = Column(String, nullable=False)
    academic_year = Column(String, nullable=True)
    semester = Column(String, nullable=False)
    subject = Column(String, nullable=False, index=True)
    predicted_questions = Column(Text, nullable=True)  # Markdown formatted questions
    text_length = Column(Integer, nullable=True)  # Length of extracted text
    processed_by = Column(String, nullable=False, index=True)  # User ID who triggered processing
    status = Column(String, nullable=False, default='processing')  # completed, processing, failed
    error_message = Column(Text, nullable=True)  # Error details if failed
    s3_key = Column(String, nullable=True)  # S3 key for backup storage
    prediction_metadata = Column(JSON, nullable=True)  # Additional metadata as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    class Config:
        orm_mode = True 