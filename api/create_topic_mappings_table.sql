-- SQL script to create the topic_mappings table
-- For PostgreSQL database

CREATE TABLE IF NOT EXISTS topic_mappings (
    id SERIAL PRIMARY KEY,
    topic_slug VARCHAR(255) NOT NULL,
    pci_topic VARCHAR(500) NOT NULL,
    university_topic VARCHAR(500) NOT NULL,
    university_subject_code VARCHAR(50) NOT NULL,
    university_unit_number INTEGER NOT NULL,
    university_name VARCHAR(100),
    regulation VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_topic_mappings_topic_slug ON topic_mappings(topic_slug);
CREATE INDEX IF NOT EXISTS idx_topic_mappings_university_subject_code ON topic_mappings(university_subject_code);
CREATE INDEX IF NOT EXISTS idx_topic_mappings_university_name ON topic_mappings(university_name);

-- Create a composite index for common queries
CREATE INDEX IF NOT EXISTS idx_topic_mappings_university_subject ON topic_mappings(university_name, university_subject_code, university_unit_number);

-- Create unique constraint on university topic (one mapping per university topic)
CREATE UNIQUE INDEX IF NOT EXISTS idx_topic_mappings_unique_university_topic 
ON topic_mappings(university_subject_code, university_unit_number, university_topic);

-- Add comments
COMMENT ON TABLE topic_mappings IS 'Maps university curriculum topics to PCI topics with topic slugs';
COMMENT ON COLUMN topic_mappings.topic_slug IS 'Topic slug (e.g., structure-of-cell) - matches content_library.topic_slug';
COMMENT ON COLUMN topic_mappings.pci_topic IS 'PCI topic name';
COMMENT ON COLUMN topic_mappings.university_topic IS 'University topic name (e.g., JNTU topic)';

