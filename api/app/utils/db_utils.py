from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List, Dict, Any
from ..models.notes import GeneratedNotes
from ..config.database import get_db

def save_notes_to_db(
    db: Session,
    notes_id: str,
    document_id: str,
    user_id: str,
    notes_content: str,
    metadata: Dict[str, Any]
) -> GeneratedNotes:
    """Save generated notes to PostgreSQL database"""
    try:
        db_notes = GeneratedNotes(
            id=notes_id,
            document_id=document_id,
            user_id=user_id,
            notes_content=notes_content,
            course_name=metadata.get('course_name'),
            subject_name=metadata.get('subject_name'),
            unit_name=metadata.get('unit_name'),
            topic=metadata.get('topic'),
            document_name=metadata.get('document_name'),
            content_length=metadata.get('content_length'),
            notes_length=metadata.get('notes_length'),
            s3_key=metadata.get('s3_key'),
            notes_metadata=metadata
        )
        
        db.add(db_notes)
        db.commit()
        db.refresh(db_notes)
        return db_notes
    except Exception as e:
        db.rollback()
        raise e

def get_notes_by_document_id(db: Session, document_id: str) -> Optional[GeneratedNotes]:
    """Get notes by document ID"""
    try:
        return db.query(GeneratedNotes).filter(
            GeneratedNotes.document_id == document_id
        ).first()
    except Exception as e:
        raise e

def get_notes_by_id(db: Session, notes_id: str) -> Optional[GeneratedNotes]:
    """Get notes by notes ID"""
    try:
        return db.query(GeneratedNotes).filter(
            GeneratedNotes.id == notes_id
        ).first()
    except Exception as e:
        raise e

def get_notes_by_user_id(db: Session, user_id: str) -> List[GeneratedNotes]:
    """Get all notes for a specific user"""
    try:
        return db.query(GeneratedNotes).filter(
            GeneratedNotes.user_id == user_id
        ).order_by(GeneratedNotes.created_at.desc()).all()
    except Exception as e:
        raise e

def delete_notes_by_id(db: Session, notes_id: str, user_id: str) -> bool:
    """Delete notes by ID (with user verification)"""
    try:
        notes = db.query(GeneratedNotes).filter(
            and_(
                GeneratedNotes.id == notes_id,
                GeneratedNotes.user_id == user_id
            )
        ).first()
        
        if notes:
            db.delete(notes)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        raise e

def update_notes_content(
    db: Session,
    notes_id: str,
    user_id: str,
    new_content: str,
    metadata: Dict[str, Any]
) -> Optional[GeneratedNotes]:
    """Update notes content"""
    try:
        notes = db.query(GeneratedNotes).filter(
            and_(
                GeneratedNotes.id == notes_id,
                GeneratedNotes.user_id == user_id
            )
        ).first()
        
        if notes:
            notes.notes_content = new_content
            notes.notes_length = len(new_content)
            notes.notes_metadata = metadata
            db.commit()
            db.refresh(notes)
            return notes
        return None
    except Exception as e:
        db.rollback()
        raise e

def check_notes_exist(db: Session, document_id: str) -> bool:
    """Check if notes exist for a document"""
    try:
        notes = db.query(GeneratedNotes).filter(
            GeneratedNotes.document_id == document_id
        ).first()
        return notes is not None
    except Exception as e:
        raise e 