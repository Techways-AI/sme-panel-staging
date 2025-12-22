from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.sql import func
from ..config.database import Base

class ContentLibrary(Base):
    __tablename__ = "content_library"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    topic_slug = Column(String, nullable=False, index=True)
    topic_name = Column(String, nullable=True)  # Human-readable topic name (e.g., "Structure of Cell")
    s3_key = Column(String, nullable=False, unique=True, index=True)
    file_type = Column(String, nullable=False)  # 'video', 'notes', 'document'
    uploaded_via = Column(String, nullable=False, default='PCI')  # 'PCI', 'University', etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    class Config:
        from_attributes = True

