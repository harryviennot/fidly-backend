-- Migration: Google Wallet v2 - Strip pre-generation and schema improvements
-- Builds on migration 12_google_wallet_support.sql

-- ============================================
-- 1. ADD google_class_id TO BUSINESSES TABLE
-- ============================================
-- Simpler than separate table: one class per business
-- Format: "{issuerId}.{business_id}"
ALTER TABLE businesses
ADD COLUMN IF NOT EXISTS google_class_id TEXT;

COMMENT ON COLUMN businesses.google_class_id IS 'Google Wallet class ID for this business. Format: {issuerId}.{businessId}';

-- ============================================
-- 2. STRIP IMAGES TABLE (Pre-generated URLs)
-- ============================================
-- Stores pre-generated strip image URLs for both Apple and Google Wallet
-- Generated synchronously on design creation, async on active design updates
CREATE TABLE IF NOT EXISTS strip_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    design_id UUID NOT NULL REFERENCES card_designs(id) ON DELETE CASCADE,
    stamp_count INT NOT NULL CHECK (stamp_count >= 0),
    platform TEXT NOT NULL CHECK (platform IN ('apple', 'google')),
    resolution TEXT NOT NULL,  -- '1x', '2x', '3x' for Apple; 'hero' for Google
    url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- One URL per design/stamp/platform/resolution combination
    UNIQUE(design_id, stamp_count, platform, resolution)
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_strip_images_design
ON strip_images(design_id);

CREATE INDEX IF NOT EXISTS idx_strip_images_lookup
ON strip_images(design_id, stamp_count, platform);

-- RLS - service role manages strip images
ALTER TABLE strip_images ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage strip_images"
ON strip_images FOR ALL
USING (true);

-- ============================================
-- 3. GOOGLE CALLBACK NONCES (Deduplication)
-- ============================================
-- Prevents processing duplicate Google Wallet callbacks
CREATE TABLE IF NOT EXISTS google_callback_nonces (
    nonce TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for cleanup queries (delete old nonces)
CREATE INDEX IF NOT EXISTS idx_nonces_processed
ON google_callback_nonces(processed_at);

-- ============================================
-- 4. CLEANUP: Remove card_design_id from google_wallet_classes
-- ============================================
-- We don't need this column - class is per business, not per design
-- The class gets updated when active design changes
-- Note: This column was added in migration 12, but our architecture
-- stores google_class_id on businesses table instead
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'google_wallet_classes'
        AND column_name = 'card_design_id'
    ) THEN
        -- First drop the foreign key constraint if it exists
        ALTER TABLE google_wallet_classes
        DROP CONSTRAINT IF EXISTS google_wallet_classes_card_design_id_fkey;

        -- Drop the index if it exists
        DROP INDEX IF EXISTS idx_google_wallet_classes_design;

        -- Then drop the column
        ALTER TABLE google_wallet_classes
        DROP COLUMN card_design_id;
    END IF;
END $$;

-- ============================================
-- 5. HELPER FUNCTION: Cleanup old nonces
-- ============================================
-- Can be called periodically to clean up old nonces (older than 7 days)
CREATE OR REPLACE FUNCTION cleanup_old_callback_nonces()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM google_callback_nonces
    WHERE processed_at < NOW() - INTERVAL '7 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
