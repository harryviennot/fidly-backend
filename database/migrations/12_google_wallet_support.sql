-- Migration: Add Google Wallet support
-- Extends push_registrations for both Apple and Google Wallet
-- Adds google_wallet_classes table for LoyaltyClass management

-- ============================================
-- EXTEND push_registrations FOR GOOGLE WALLET
-- ============================================

-- Add wallet_type column to distinguish Apple vs Google registrations
ALTER TABLE push_registrations
ADD COLUMN IF NOT EXISTS wallet_type TEXT NOT NULL DEFAULT 'apple';

-- Add constraint for valid wallet types
ALTER TABLE push_registrations
ADD CONSTRAINT push_registrations_wallet_type_check
CHECK (wallet_type IN ('apple', 'google'));

-- Add Google Wallet-specific field for object ID
ALTER TABLE push_registrations
ADD COLUMN IF NOT EXISTS google_object_id TEXT;

-- Make Apple-specific columns nullable for Google entries
-- (Google doesn't use device_library_id or push_token)
ALTER TABLE push_registrations ALTER COLUMN device_library_id DROP NOT NULL;
ALTER TABLE push_registrations ALTER COLUMN push_token DROP NOT NULL;

-- Drop the existing unique constraint that requires device_library_id
ALTER TABLE push_registrations DROP CONSTRAINT IF EXISTS push_registrations_customer_id_device_library_id_key;

-- Create separate unique indexes for Apple and Google
-- Apple: unique on (customer_id, device_library_id)
CREATE UNIQUE INDEX IF NOT EXISTS push_registrations_unique_apple
ON push_registrations(customer_id, device_library_id)
WHERE wallet_type = 'apple' AND device_library_id IS NOT NULL;

-- Google: unique on (customer_id, google_object_id)
CREATE UNIQUE INDEX IF NOT EXISTS push_registrations_unique_google
ON push_registrations(customer_id, google_object_id)
WHERE wallet_type = 'google' AND google_object_id IS NOT NULL;

-- Index for efficient lookups by wallet type
CREATE INDEX IF NOT EXISTS idx_push_registrations_wallet_type
ON push_registrations(wallet_type);

-- ============================================
-- GOOGLE WALLET CLASSES TABLE
-- ============================================

-- Stores Google Wallet LoyaltyClass records (one per business)
CREATE TABLE IF NOT EXISTS google_wallet_classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    card_design_id UUID REFERENCES card_designs(id) ON DELETE SET NULL,
    class_id TEXT NOT NULL UNIQUE,  -- Format: "issuer_id.business_id"
    class_data JSONB,  -- Cached class configuration sent to Google
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(business_id)  -- One class per business
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_google_wallet_classes_business
ON google_wallet_classes(business_id);

CREATE INDEX IF NOT EXISTS idx_google_wallet_classes_design
ON google_wallet_classes(card_design_id);

-- Trigger to auto-update updated_at
CREATE TRIGGER update_google_wallet_classes_updated_at
    BEFORE UPDATE ON google_wallet_classes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE google_wallet_classes ENABLE ROW LEVEL SECURITY;

-- Business members can view their classes
CREATE POLICY "Business members can view their google_wallet_classes"
ON google_wallet_classes FOR SELECT
USING (
    business_id IN (
        SELECT business_id FROM memberships WHERE user_id = auth.uid()
    )
);

-- Business owners/admins can manage classes
CREATE POLICY "Business owners can insert google_wallet_classes"
ON google_wallet_classes FOR INSERT
WITH CHECK (
    business_id IN (
        SELECT business_id FROM memberships
        WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
    )
);

CREATE POLICY "Business owners can update google_wallet_classes"
ON google_wallet_classes FOR UPDATE
USING (
    business_id IN (
        SELECT business_id FROM memberships
        WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
    )
);

CREATE POLICY "Business owners can delete google_wallet_classes"
ON google_wallet_classes FOR DELETE
USING (
    business_id IN (
        SELECT business_id FROM memberships
        WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
    )
);

-- ============================================
-- GOOGLE NOTIFICATION TRACKING TABLE
-- ============================================

-- Track Google Wallet notifications to respect 3/24h limit
CREATE TABLE IF NOT EXISTS google_wallet_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    google_object_id TEXT NOT NULL,
    notification_type TEXT NOT NULL CHECK (notification_type IN ('stamp', 'reward', 'design')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for efficient rate limit checks
CREATE INDEX IF NOT EXISTS idx_google_notifications_customer_time
ON google_wallet_notifications(customer_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_google_notifications_object
ON google_wallet_notifications(google_object_id);

-- Auto-delete old notifications (older than 24 hours) - cleanup function
CREATE OR REPLACE FUNCTION cleanup_old_google_notifications()
RETURNS void AS $$
BEGIN
    DELETE FROM google_wallet_notifications
    WHERE created_at < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;

-- RLS for notification tracking
ALTER TABLE google_wallet_notifications ENABLE ROW LEVEL SECURITY;

-- Service role can manage notifications (backend uses service role)
CREATE POLICY "Service role can manage google_wallet_notifications"
ON google_wallet_notifications FOR ALL
USING (true);
