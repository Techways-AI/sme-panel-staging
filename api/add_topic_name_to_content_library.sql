-- Migration script to add topic_name column to content_library table
-- This column stores the human-readable topic name (e.g., "Structure of Cell")
-- while topic_slug stores the slug version (e.g., "structure-of-cell")

ALTER TABLE content_library 
ADD COLUMN IF NOT EXISTS topic_name VARCHAR(500);

-- Add comment
COMMENT ON COLUMN content_library.topic_name IS 'Human-readable topic name (e.g., "Structure of Cell")';

