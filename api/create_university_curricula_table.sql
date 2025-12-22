-- Create university_curricula table with integer sequential IDs (1, 2, 3...)
CREATE TABLE IF NOT EXISTS university_curricula (
    id SERIAL PRIMARY KEY,
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
CREATE INDEX IF NOT EXISTS idx_university_curricula_id ON university_curricula(id);
CREATE INDEX IF NOT EXISTS idx_university_curricula_university ON university_curricula(university);
CREATE INDEX IF NOT EXISTS idx_university_curricula_regulation ON university_curricula(regulation);
CREATE INDEX IF NOT EXISTS idx_university_curricula_course ON university_curricula(course);
CREATE INDEX IF NOT EXISTS idx_university_curricula_curriculum_type ON university_curricula(curriculum_type);
CREATE INDEX IF NOT EXISTS idx_university_curricula_status ON university_curricula(status);

-- Add comment to table
COMMENT ON TABLE university_curricula IS 'Stores university and PCI curriculum data with sequential integer IDs';

