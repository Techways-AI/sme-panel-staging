-- Migration script to remove pci_subject_code, pci_unit_number, and pci_unit_title columns
-- from the topic_mappings table

-- Drop the columns
ALTER TABLE topic_mappings 
DROP COLUMN IF EXISTS pci_subject_code,
DROP COLUMN IF EXISTS pci_unit_number,
DROP COLUMN IF EXISTS pci_unit_title;

-- Drop the index on pci_subject_code if it exists
DROP INDEX IF EXISTS idx_topic_mappings_pci_subject_code;

