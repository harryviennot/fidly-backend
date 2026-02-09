-- Add strip_background_opacity column to card_designs
-- Default 40 (percent) matches the previously hardcoded value
ALTER TABLE card_designs ADD COLUMN IF NOT EXISTS strip_background_opacity INTEGER NOT NULL DEFAULT 40;
