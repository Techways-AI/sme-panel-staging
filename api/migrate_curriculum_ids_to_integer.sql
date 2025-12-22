-- Migration script to change curriculum IDs from UUID strings to sequential integers
-- OPTION 1: REPLACE existing id column (recommended - simpler)
-- This replaces the UUID id column with sequential integers (1, 2, 3...)
-- WARNING: This will lose the original UUID values. Backup your database first!

-- Step 1: Drop the existing primary key constraint
ALTER TABLE university_curricula DROP CONSTRAINT IF EXISTS university_curricula_pkey;

-- Step 2: Add a new integer column for the ID
ALTER TABLE university_curricula ADD COLUMN id_new INTEGER;

-- Step 3: Populate the new column with sequential numbers
-- This assigns 1, 2, 3, etc. based on created_at order
WITH numbered AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY created_at) as rn
    FROM university_curricula
)
UPDATE university_curricula
SET id_new = numbered.rn
FROM numbered
WHERE university_curricula.id = numbered.id;

-- Step 4: Drop the old id column
ALTER TABLE university_curricula DROP COLUMN id;

-- Step 5: Rename the new column to id
ALTER TABLE university_curricula RENAME COLUMN id_new TO id;

-- Step 6: Set it as primary key with auto-increment
ALTER TABLE university_curricula 
    ALTER COLUMN id SET NOT NULL,
    ADD PRIMARY KEY (id);

-- Step 7: Create a sequence for auto-increment
CREATE SEQUENCE IF NOT EXISTS university_curricula_id_seq OWNED BY university_curricula.id;
ALTER TABLE university_curricula 
    ALTER COLUMN id SET DEFAULT nextval('university_curricula_id_seq');
SELECT setval('university_curricula_id_seq', (SELECT MAX(id) FROM university_curricula));

-- ============================================================================
-- OPTION 2: KEEP UUID column and add sequential id (if you want both)
-- Uncomment below if you want to keep uuid_id and add a new sequential id
-- ============================================================================
-- Step 1: Rename existing id to uuid_id
-- ALTER TABLE university_curricula RENAME COLUMN id TO uuid_id;

-- Step 2: Add new integer id column
-- ALTER TABLE university_curricula ADD COLUMN id INTEGER;

-- Step 3: Populate with sequential numbers
-- WITH numbered AS (
--     SELECT uuid_id, ROW_NUMBER() OVER (ORDER BY created_at) as rn
--     FROM university_curricula
-- )
-- UPDATE university_curricula
-- SET id = numbered.rn
-- FROM numbered
-- WHERE university_curricula.uuid_id = numbered.uuid_id;

-- Step 4: Set as primary key
-- ALTER TABLE university_curricula 
--     ALTER COLUMN id SET NOT NULL,
--     DROP CONSTRAINT IF EXISTS university_curricula_pkey,
--     ADD PRIMARY KEY (id);

-- Step 5: Create sequence
-- CREATE SEQUENCE IF NOT EXISTS university_curricula_id_seq OWNED BY university_curricula.id;
-- ALTER TABLE university_curricula 
--     ALTER COLUMN id SET DEFAULT nextval('university_curricula_id_seq');
-- SELECT setval('university_curricula_id_seq', (SELECT MAX(id) FROM university_curricula));

-- Step 8: Update any foreign key references if they exist
-- (Adjust table/column names as needed for your schema)
-- ALTER TABLE other_table 
--     ALTER COLUMN curriculum_id TYPE INTEGER USING curriculum_id::INTEGER;

