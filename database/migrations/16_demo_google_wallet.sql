-- Migration: Add Google Wallet support to demo tables
-- Extends demo_push_registrations for both Apple and Google Wallet

-- ============================================
-- EXTEND demo_push_registrations FOR GOOGLE WALLET
-- ============================================

-- Add wallet_type column to distinguish Apple vs Google registrations
ALTER TABLE demo_push_registrations
ADD COLUMN IF NOT EXISTS wallet_type TEXT NOT NULL DEFAULT 'apple';

-- Add constraint for valid wallet types
ALTER TABLE demo_push_registrations
ADD CONSTRAINT demo_push_registrations_wallet_type_check
CHECK (wallet_type IN ('apple', 'google'));

-- Add Google Wallet-specific field for object ID
ALTER TABLE demo_push_registrations
ADD COLUMN IF NOT EXISTS google_object_id TEXT;

-- Make Apple-specific columns nullable for Google entries
-- (Google doesn't use device_library_id or push_token)
ALTER TABLE demo_push_registrations ALTER COLUMN device_library_id DROP NOT NULL;
ALTER TABLE demo_push_registrations ALTER COLUMN push_token DROP NOT NULL;

-- Drop the existing unique constraint that requires device_library_id
ALTER TABLE demo_push_registrations DROP CONSTRAINT IF EXISTS demo_push_registrations_demo_customer_id_device_library_id_key;

-- Create unique constraint for Apple Wallet (uses device_library_id)
ALTER TABLE demo_push_registrations
ADD CONSTRAINT demo_push_registrations_unique_key
UNIQUE (demo_customer_id, device_library_id, wallet_type);

-- Create unique constraint for Google Wallet (uses google_object_id)
ALTER TABLE demo_push_registrations
ADD CONSTRAINT demo_push_registrations_google_unique_key
UNIQUE (demo_customer_id, google_object_id);

-- Index for efficient lookups by wallet type
CREATE INDEX IF NOT EXISTS idx_demo_push_registrations_wallet_type
ON demo_push_registrations(wallet_type);

-- ============================================
-- TRACK WALLET PROVIDER IN SESSIONS (optional)
-- ============================================

-- Track which wallet provider was used for this demo session
ALTER TABLE demo_sessions
ADD COLUMN IF NOT EXISTS wallet_provider TEXT;

ALTER TABLE demo_sessions
ADD CONSTRAINT demo_sessions_wallet_provider_check
CHECK (wallet_provider IS NULL OR wallet_provider IN ('apple', 'google'));
