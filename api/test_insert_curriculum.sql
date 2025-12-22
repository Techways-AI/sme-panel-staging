-- Test query to verify table structure
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM 
    information_schema.columns
WHERE 
    table_name = 'university_curricula'
ORDER BY 
    ordinal_position;

-- Check row count (should be 0 if table is empty)
SELECT COUNT(*) as total_rows FROM university_curricula;

-- If you want to insert a test record manually (optional):
-- Note: This is just for testing. Normally data is added via the API.
/*
INSERT INTO university_curricula (
    id,
    university,
    regulation,
    course,
    curriculum_type,
    curriculum_data,
    status
) VALUES (
    'test-id-123',
    'Test University',
    'R20',
    'B.Pharm',
    'university',
    '{"years": [{"year": 1, "semesters": [{"semester": 1, "subjects": []}]}]}'::jsonb,
    'active'
);
*/

