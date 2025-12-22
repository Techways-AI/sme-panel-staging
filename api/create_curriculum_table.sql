-- SQL script to create the university_curricula table
-- For PostgreSQL database

CREATE TABLE IF NOT EXISTS university_curricula (
    id VARCHAR(255) PRIMARY KEY,
    university VARCHAR(255) NOT NULL,
    regulation VARCHAR(255) NOT NULL,
    course VARCHAR(255) NOT NULL,
    effective_year VARCHAR(50),
    curriculum_type VARCHAR(50) NOT NULL DEFAULT 'university',
    curriculum_data JSONB NOT NULL,
    stats JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(255)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_university_curricula_university ON university_curricula(university);
CREATE INDEX IF NOT EXISTS idx_university_curricula_regulation ON university_curricula(regulation);
CREATE INDEX IF NOT EXISTS idx_university_curricula_course ON university_curricula(course);
CREATE INDEX IF NOT EXISTS idx_university_curricula_status ON university_curricula(status);
CREATE INDEX IF NOT EXISTS idx_university_curricula_type ON university_curricula(curriculum_type);

-- Create a composite index for common queries
CREATE INDEX IF NOT EXISTS idx_university_curricula_lookup ON university_curricula(university, regulation, course, status);

-- Add comment to table
COMMENT ON TABLE university_curricula IS 'Stores university curriculum data including subjects, units, and topics';
COMMENT ON COLUMN university_curricula.curriculum_data IS 'Full curriculum structure in JSON format';
COMMENT ON COLUMN university_curricula.stats IS 'Calculated statistics (subjects, units, topics counts)';
COMMENT ON COLUMN university_curricula.curriculum_type IS 'Type of curriculum: university or pci';

