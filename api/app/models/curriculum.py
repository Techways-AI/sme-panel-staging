from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Boolean
from sqlalchemy.sql import func
from ..config.database import Base

class UniversityCurriculum(Base):
    __tablename__ = "university_curricula"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    university = Column(String, nullable=False, index=True)
    regulation = Column(String, nullable=False, index=True)
    course = Column(String, nullable=False, index=True)
    effective_year = Column(String, nullable=True)
    curriculum_type = Column(String, nullable=False, default="university")  # "university" or "pci"
    curriculum_data = Column(JSON, nullable=False)  # Full curriculum structure
    stats = Column(JSON, nullable=True)  # Calculated statistics
    status = Column(String, nullable=False, default="active")  # "active" or "inactive"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String, nullable=True)
    
    class Config:
        orm_mode = True

