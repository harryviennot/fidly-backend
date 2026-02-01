-- Migration: Add icon customization columns to card_designs table
-- Enables predefined Phosphor icons, icon colors, and custom strip backgrounds

-- Stamp icon (predefined icon name for regular stamps)
ALTER TABLE card_designs ADD COLUMN IF NOT EXISTS stamp_icon TEXT DEFAULT 'checkmark';

-- Reward icon (predefined icon name for the last/reward stamp)
ALTER TABLE card_designs ADD COLUMN IF NOT EXISTS reward_icon TEXT DEFAULT 'gift';

-- Icon color (rgb color for the icon inside stamps)
ALTER TABLE card_designs ADD COLUMN IF NOT EXISTS icon_color TEXT DEFAULT 'rgb(255, 255, 255)';

-- Strip background image path (custom background for the strip)
ALTER TABLE card_designs ADD COLUMN IF NOT EXISTS strip_background_path TEXT;
