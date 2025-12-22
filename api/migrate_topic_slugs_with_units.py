"""
Migration script to update topic_mappings table:
1. Populate pci_subject_code and pci_unit_number from PCI curriculum data
2. Regenerate topic_slug with unit context for uniqueness

Run this script after adding the new columns to the database.
"""

import sys
import os
import json
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.orm import Session
from app.config.database import get_db, engine
from app.models.topic_mapping import TopicMapping
from app.models.curriculum import Curriculum
from app.utils.content_library_utils import generate_topic_slug

def find_pci_topic_info(pci_topic_name: str, db: Session) -> tuple[str | None, int | None, str | None]:
    """
    Find PCI subject code, unit number, and unit title for a given PCI topic name.
    Searches through all PCI curriculum data.
    
    Returns:
        (subject_code, unit_number, unit_title) or (None, None, None) if not found
    """
    # Get all PCI curricula
    pci_curricula = db.query(Curriculum).filter(
        Curriculum.curriculum_type == "pci"
    ).all()
    
    for curriculum in pci_curricula:
        if not curriculum.curriculum_data:
            continue
            
        years = curriculum.curriculum_data.get("years", [])
        
        for year in years:
            semesters = year.get("semesters", [])
            
            for semester in semesters:
                subjects = semester.get("subjects", [])
                
                for subject in subjects:
                    units = subject.get("units", [])
                    
                    for unit_idx, unit in enumerate(units):
                        topics = unit.get("topics", [])
                        
                        for topic in topics:
                            # Handle both string and object formats
                            topic_name = topic if isinstance(topic, str) else topic.get("name", "")
                            
                            # Normalize for comparison (case-insensitive, trim whitespace)
                            if topic_name.strip().lower() == pci_topic_name.strip().lower():
                                # Found the topic! Extract unit info
                                unit_number = unit.get("number")
                                if unit_number is None:
                                    # Fallback to index + 1
                                    unit_number = unit_idx + 1
                                elif isinstance(unit_number, str):
                                    # Try to extract number from string
                                    import re
                                    num_match = re.search(r'\d+', unit_number)
                                    if num_match:
                                        unit_number = int(num_match.group())
                                    else:
                                        unit_number = unit_idx + 1
                                
                                unit_title = unit.get("title") or unit.get("name") or f"Unit {unit_number}"
                                subject_code = subject.get("code", "")
                                
                                return (subject_code, unit_number, unit_title)
    
    return (None, None, None)

def migrate_topic_slugs(db: Session):
    """
    Migrate existing topic_mappings to include unit information in slugs.
    """
    print("Starting migration of topic_mappings slugs...")
    
    # Get all topic mappings
    mappings = db.query(TopicMapping).all()
    total = len(mappings)
    updated = 0
    skipped = 0
    errors = 0
    
    print(f"Found {total} topic mappings to process")
    
    for mapping in mappings:
        try:
            # Check if unit info is already populated
            if mapping.pci_subject_code and mapping.pci_unit_number:
                # Unit info exists, just regenerate slug
                new_slug = generate_topic_slug(
                    mapping.pci_topic,
                    unit_number=mapping.pci_unit_number,
                    subject_code=mapping.pci_subject_code
                )
                
                if new_slug != mapping.topic_slug:
                    mapping.topic_slug = new_slug
                    updated += 1
                    print(f"  Updated slug for ID {mapping.id}: {mapping.topic_slug} -> {new_slug}")
                else:
                    skipped += 1
            else:
                # Need to look up unit info from PCI curriculum
                subject_code, unit_number, unit_title = find_pci_topic_info(mapping.pci_topic, db)
                
                if subject_code and unit_number:
                    # Found unit info, update the record
                    mapping.pci_subject_code = subject_code
                    mapping.pci_unit_number = unit_number
                    mapping.pci_unit_title = unit_title
                    
                    # Regenerate slug with unit context
                    new_slug = generate_topic_slug(
                        mapping.pci_topic,
                        unit_number=unit_number,
                        subject_code=subject_code
                    )
                    mapping.topic_slug = new_slug
                    
                    updated += 1
                    print(f"  Updated ID {mapping.id}: Added unit info and new slug: {new_slug}")
                else:
                    # Could not find unit info - keep old slug
                    skipped += 1
                    print(f"  Skipped ID {mapping.id}: Could not find unit info for '{mapping.pci_topic}'")
        
        except Exception as e:
            errors += 1
            print(f"  Error processing ID {mapping.id}: {str(e)}")
    
    # Commit all changes
    try:
        db.commit()
        print(f"\nMigration complete!")
        print(f"  Total: {total}")
        print(f"  Updated: {updated}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors: {errors}")
    except Exception as e:
        db.rollback()
        print(f"\nError committing changes: {str(e)}")
        raise

if __name__ == "__main__":
    print("Topic Mappings Slug Migration Script")
    print("=" * 50)
    
    # Get database session
    db = next(get_db())
    
    try:
        migrate_topic_slugs(db)
    except Exception as e:
        print(f"\nMigration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

