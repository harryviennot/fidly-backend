-- Migration 14: Fix push_registrations unique constraint for PostgREST upsert
--
-- Problem: Migration 12 created partial unique indexes that don't work with
-- PostgREST's ON CONFLICT clause, causing 500 errors on Apple Wallet device registration.
--
-- Solution: Add a proper unique constraint that includes wallet_type, allowing
-- the upsert pattern to work correctly while still supporting multiple devices
-- per customer and both Apple + Google Wallet registrations.

-- Add composite unique constraint that includes wallet_type
-- This allows:
-- - Same customer on multiple Apple devices (different device_library_id)
-- - Same customer with Apple + Google Wallet (different wallet_type)
-- - Atomic upsert operations via PostgREST
ALTER TABLE push_registrations
ADD CONSTRAINT push_registrations_customer_device_wallet_unique
UNIQUE (customer_id, device_library_id, wallet_type);
