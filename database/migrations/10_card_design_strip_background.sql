-- Add strip_background_path column to card_designs table
-- This stores the path to the custom strip background image in Supabase storage

ALTER TABLE card_designs
ADD COLUMN IF NOT EXISTS strip_background_path TEXT;

-- Add comment for documentation
COMMENT ON COLUMN card_designs.strip_background_path IS 'Path to custom strip background image in Supabase storage (businesses bucket)';
