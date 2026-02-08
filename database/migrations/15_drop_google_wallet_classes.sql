-- Migration: Drop unused google_wallet_classes table
-- This table was created but never used by the application.
-- Google Wallet classes are managed directly via API calls without local caching.

DROP TABLE IF EXISTS google_wallet_classes;
