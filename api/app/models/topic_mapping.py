from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.sql import func
from ..config.database import Base

class TopicMapping(Base):
    __tablename__ = "topic_mappings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    topic_slug = Column(String, nullable=False, index=True)  # Not unique - multiple university topics can map to same PCI topic
    pci_topic = Column(String, nullable=False)
    pci_subject_code = Column(String, nullable=True)  # PCI subject code (e.g., "BP101T")
    pci_unit_number = Column(Integer, nullable=True)  # PCI unit number
    pci_unit_title = Column(String, nullable=True)  # PCI unit title
    university_topic = Column(String, nullable=False)
    university_subject_code = Column(String, nullable=False)
    university_unit_number = Column(Integer, nullable=False)
    university_name = Column(String, nullable=True)  # e.g., "JNTU", "Anna University"
    regulation = Column(String, nullable=True)  # e.g., "R20", "R23"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    class Config:
        orm_mode = True

