-- Add stamp_icon and reward_icon columns to card_designs table
-- These store the icon type used for stamps and the final reward stamp

ALTER TABLE card_designs
ADD COLUMN IF NOT EXISTS stamp_icon TEXT DEFAULT 'checkmark',
ADD COLUMN IF NOT EXISTS reward_icon TEXT DEFAULT 'gift';

-- Add comment for documentation
COMMENT ON COLUMN card_designs.stamp_icon IS 'Icon type for regular stamps (e.g., checkmark, coffee, star, trophy)';
COMMENT ON COLUMN card_designs.reward_icon IS 'Icon type for the final reward stamp (e.g., gift, trophy, crown, sparkle)';
