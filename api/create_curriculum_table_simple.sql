-- Simple SQL script to create the university_curricula table
-- Run this in your PostgreSQL database

CREATE TABLE university_curricula (
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

CREATE INDEX idx_university_curricula_university ON university_curricula(university);
CREATE INDEX idx_university_curricula_regulation ON university_curricula(regulation);
CREATE INDEX idx_university_curricula_course ON university_curricula(course);

