-- Migration: Add strip_status to card_designs
-- Tracks the regeneration status of strip images for a design

-- Add strip_status column with default 'ready'
ALTER TABLE card_designs
ADD COLUMN IF NOT EXISTS strip_status TEXT NOT NULL DEFAULT 'ready';

-- Add constraint for valid status values
ALTER TABLE card_designs
ADD CONSTRAINT card_designs_strip_status_check
CHECK (strip_status IN ('ready', 'regenerating'));

-- Comment for documentation
COMMENT ON COLUMN card_designs.strip_status IS 'Status of strip image generation: ready (can be activated), regenerating (in progress)';
