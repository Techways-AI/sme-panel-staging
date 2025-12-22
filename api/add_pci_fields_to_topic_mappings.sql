-- Migration script to add PCI subject and unit fields to topic_mappings table
-- Run this script to add the new columns for storing PCI subject code, unit number, and unit title

ALTER TABLE topic_mappings 
ADD COLUMN IF NOT EXISTS pci_subject_code VARCHAR(50),
ADD COLUMN IF NOT EXISTS pci_unit_number INTEGER,
ADD COLUMN IF NOT EXISTS pci_unit_title VARCHAR(500);

-- Add comments
COMMENT ON COLUMN topic_mappings.pci_subject_code IS 'PCI subject code (e.g., BP101T)';
COMMENT ON COLUMN topic_mappings.pci_unit_number IS 'PCI unit number';
COMMENT ON COLUMN topic_mappings.pci_unit_title IS 'PCI unit title';

