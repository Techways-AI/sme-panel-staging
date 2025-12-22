-- SQL script to create the content_library table
-- For PostgreSQL database

CREATE TABLE IF NOT EXISTS content_library (
    id SERIAL PRIMARY KEY,
    topic_slug VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500) NOT NULL UNIQUE,
    file_type VARCHAR(50) NOT NULL,
    uploaded_via VARCHAR(50) NOT NULL DEFAULT 'PCI',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_content_library_topic_slug ON content_library(topic_slug);
CREATE INDEX IF NOT EXISTS idx_content_library_s3_key ON content_library(s3_key);
CREATE INDEX IF NOT EXISTS idx_content_library_file_type ON content_library(file_type);
CREATE INDEX IF NOT EXISTS idx_content_library_uploaded_via ON content_library(uploaded_via);

-- Create a composite index for common queries
CREATE INDEX IF NOT EXISTS idx_content_library_topic_file_type ON content_library(topic_slug, file_type);

-- Add comment to table
COMMENT ON TABLE content_library IS 'Stores content library indexing linking topic slugs to S3 keys';
COMMENT ON COLUMN content_library.topic_slug IS 'Topic slug (e.g., structure-of-cell)';
COMMENT ON COLUMN content_library.s3_key IS 'S3 key path (e.g., bpharm/pci/1-1/hap/unit1/structure-of-cell.mp4)';
COMMENT ON COLUMN content_library.file_type IS 'File type: video, notes, or document';
COMMENT ON COLUMN content_library.uploaded_via IS 'Upload source: PCI, University, etc.';

