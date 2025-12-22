-- Migration script to fix the unique constraint on topic_mappings table
-- Run this if you already created the table with the UNIQUE constraint on topic_slug

-- Step 1: Drop the unique constraint on topic_slug
ALTER TABLE topic_mappings DROP CONSTRAINT IF EXISTS topic_mappings_topic_slug_key;

-- Step 2: Add a composite unique constraint on university topic
-- This ensures each university topic can only be mapped once
CREATE UNIQUE INDEX IF NOT EXISTS idx_topic_mappings_unique_university_topic 
ON topic_mappings(university_subject_code, university_unit_number, university_topic);

-- Step 3: Keep the index on topic_slug (but not unique) for fast lookups
-- The index should already exist, but if not:
CREATE INDEX IF NOT EXISTS idx_topic_mappings_topic_slug ON topic_mappings(topic_slug);

