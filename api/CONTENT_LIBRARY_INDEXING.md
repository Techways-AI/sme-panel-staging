# Content Library Indexing Implementation

## Overview
This implementation adds automatic indexing to the `content_library` database table whenever documents or videos are uploaded via the SME Panel.

## Database Schema

### Table: `content_library`
```sql
CREATE TABLE content_library (
    id SERIAL PRIMARY KEY,
    topic_slug VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500) NOT NULL UNIQUE,
    file_type VARCHAR(50) NOT NULL,
    uploaded_via VARCHAR(50) NOT NULL DEFAULT 'PCI',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

## Implementation Details

### 1. Database Model
- **File**: `api/app/models/content_library.py`
- SQLAlchemy model for the `content_library` table

### 2. Utility Functions
- **File**: `api/app/utils/content_library_utils.py`
- `generate_topic_slug(topic_name)`: Converts topic names to slugs (e.g., "Structure of Cell" → "structure-of-cell")
- `get_file_type_from_filename(filename)`: Determines file type ('video', 'notes', 'document')
- `index_content_library(db, topic_slug, s3_key, file_type, uploaded_via)`: Saves record to database

### 3. Document Upload Integration
- **File**: `api/app/routers/documents.py`
- After successful S3 upload, automatically indexes the document
- Extracts topic slug from folder structure
- Determines file type from filename extension
- Uses curriculum type (default: 'PCI') as `uploaded_via`

### 4. Video Upload Integration
- **File**: `api/app/routers/videos.py`
- After successful video metadata save, automatically indexes the video
- Extracts topic slug from folder structure
- Uses 'video' as file type
- Uses curriculum type (default: 'PCI') as `uploaded_via`

## Usage

### Database Migration
Run the SQL script to create the table:
```bash
psql -U your_user -d your_database -f api/create_content_library_table.sql
```

### Automatic Indexing
Indexing happens automatically when:
1. Documents are uploaded via `/api/documents/upload`
2. Videos are uploaded via `/api/videos/upload`

### Example Flow

**Document Upload:**
1. User uploads `mitochondria.pdf` with topic "Mitochondria"
2. File uploaded to S3: `bpharma/pci/1-1/hap/unit1/mitochondria.pdf`
3. Topic slug generated: `mitochondria`
4. Record created:
   ```sql
   INSERT INTO content_library (topic_slug, s3_key, file_type, uploaded_via)
   VALUES ('mitochondria', 'bpharma/pci/1-1/hap/unit1/mitochondria.pdf', 'notes', 'PCI');
   ```

**Video Upload:**
1. User adds video URL with topic "Structure of Cell"
2. Video metadata saved to S3: `videos/pci/1-1/hap/unit1/structure-of-cell/vid-xxx/metadata.json`
3. Topic slug generated: `structure-of-cell`
4. Record created:
   ```sql
   INSERT INTO content_library (topic_slug, s3_key, file_type, uploaded_via)
   VALUES ('structure-of-cell', 'videos/pci/1-1/hap/unit1/structure-of-cell/vid-xxx/metadata.json', 'video', 'PCI');
   ```

## Error Handling

- Indexing failures do **not** cause upload failures
- All indexing errors are logged for debugging
- Database errors are caught and logged, but don't interrupt the upload process

## Notes

- The implementation preserves all existing functionality
- Indexing is non-blocking - uploads succeed even if indexing fails
- Topic slugs are generated from topic names in folder structure
- File types are determined automatically from file extensions
- The `uploaded_via` field defaults to 'PCI' but can be set based on curriculum type

