from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.sql import func
from ..config.database import Base

class GeneratedNotes(Base):
    __tablename__ = "generated_notes"

    id = Column(String, primary_key=True, index=True)  # notes_id
    document_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    notes_content = Column(Text, nullable=False)
    course_name = Column(String, nullable=True)
    subject_name = Column(String, nullable=True)
    unit_name = Column(String, nullable=True)
    topic = Column(String, nullable=True)
    document_name = Column(String, nullable=True)
    content_length = Column(Integer, nullable=True)
    notes_length = Column(Integer, nullable=True)
    s3_key = Column(String, nullable=True)  # S3 key for backup storage
    notes_metadata = Column(JSON, nullable=True)  # Additional metadata as JSON (renamed from metadata)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    class Config:
        orm_mode = True 