-- Migration: Add activity tracking to memberships
-- Date: 2025-01-30
-- Description: Adds last_active_at and scans_count to track team member activity

-- ============================================
-- 1. Add activity columns to memberships
-- ============================================

ALTER TABLE memberships
ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS scans_count INTEGER DEFAULT 0;

-- ============================================
-- 2. Create index for activity queries
-- ============================================

CREATE INDEX IF NOT EXISTS idx_memberships_last_active ON memberships(last_active_at DESC NULLS LAST);

-- ============================================
-- 3. Comments for documentation
-- ============================================

COMMENT ON COLUMN memberships.last_active_at IS 'Timestamp of last activity (scan, dashboard login, etc.)';
COMMENT ON COLUMN memberships.scans_count IS 'Total number of customer passes scanned by this team member';
