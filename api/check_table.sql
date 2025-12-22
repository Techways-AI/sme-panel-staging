-- Check if table exists and see its structure
SELECT 
    table_name,
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

-- Check if there are any rows
SELECT COUNT(*) as total_rows FROM university_curricula;

-- See all data (will be empty if table was just created)
SELECT * FROM university_curricula;

