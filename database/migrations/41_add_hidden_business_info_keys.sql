-- Add hidden_business_info_keys to card_designs
-- Stores array of business info keys to hide on a specific design
-- e.g. ["biz_hours", "biz_website"]
ALTER TABLE card_designs
ADD COLUMN IF NOT EXISTS hidden_business_info_keys JSONB DEFAULT '[]';
