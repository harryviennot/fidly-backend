-- Add primary locale to businesses (existing businesses keep 'en' to preserve current behavior)
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS primary_locale TEXT NOT NULL DEFAULT 'en';
-- New businesses default to 'fr'
ALTER TABLE businesses ALTER COLUMN primary_locale SET DEFAULT 'fr';

-- Add translations overlay to card_designs
-- Structure: { "en": { "organization_name": "...", "description": "...", "secondary_fields": [...] } }
ALTER TABLE card_designs ADD COLUMN IF NOT EXISTS translations JSONB DEFAULT '{}';
