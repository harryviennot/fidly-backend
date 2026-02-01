-- Migration: Add logo_url column to businesses table
-- Allows businesses to store their logo URL (from onboarding or external source)

ALTER TABLE businesses ADD COLUMN IF NOT EXISTS logo_url TEXT;
