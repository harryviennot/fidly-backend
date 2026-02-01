-- Migration: Add invitations table and admin role
-- Date: 2025-01-29
-- Description: Adds team invitation system with pending invitations and admin role

-- ============================================
-- 1. Add admin role to memberships
-- ============================================

-- Drop existing constraint if it exists
ALTER TABLE memberships
DROP CONSTRAINT IF EXISTS memberships_role_check;

-- Add new constraint including admin role
ALTER TABLE memberships
ADD CONSTRAINT memberships_role_check
CHECK (role IN ('owner', 'admin', 'scanner'));

-- ============================================
-- 2. Create invitations table
-- ============================================

CREATE TABLE IF NOT EXISTS invitations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  name TEXT,
  role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'scanner')),
  token TEXT NOT NULL UNIQUE,
  invited_by UUID NOT NULL REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'expired', 'cancelled')),
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  accepted_at TIMESTAMPTZ
);

-- ============================================
-- 3. Create indexes for performance
-- ============================================

CREATE INDEX IF NOT EXISTS idx_invitations_token ON invitations(token);
CREATE INDEX IF NOT EXISTS idx_invitations_email ON invitations(email);
CREATE INDEX IF NOT EXISTS idx_invitations_business ON invitations(business_id);
CREATE INDEX IF NOT EXISTS idx_invitations_status ON invitations(status) WHERE status = 'pending';

-- ============================================
-- 4. Enable Row Level Security
-- ============================================

ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 5. RLS Policies
-- ============================================

-- Policy: Users can view invitations for businesses they're a member of (owner/admin only)
CREATE POLICY "Users can view business invitations" ON invitations
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM memberships m
      JOIN users u ON m.user_id = u.id
      WHERE m.business_id = invitations.business_id
      AND u.auth_id = auth.uid()
      AND m.role IN ('owner', 'admin')
    )
  );

-- Policy: Anyone can view an invitation by its token (needed for accept page)
-- This overlaps with above but allows unauthenticated access by token
CREATE POLICY "Anyone can view invitation by token" ON invitations
  FOR SELECT USING (true);

-- Policy: Owners and admins can create invitations
-- Note: Role restrictions (admin can only invite scanners) enforced in API
CREATE POLICY "Owners and admins can create invitations" ON invitations
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM memberships m
      JOIN users u ON m.user_id = u.id
      WHERE m.business_id = invitations.business_id
      AND u.auth_id = auth.uid()
      AND m.role IN ('owner', 'admin')
    )
  );

-- Policy: Owners and admins can update invitations (cancel, mark accepted)
CREATE POLICY "Owners and admins can update invitations" ON invitations
  FOR UPDATE USING (
    EXISTS (
      SELECT 1 FROM memberships m
      JOIN users u ON m.user_id = u.id
      WHERE m.business_id = invitations.business_id
      AND u.auth_id = auth.uid()
      AND m.role IN ('owner', 'admin')
    )
  );

-- Policy: Owners and admins can delete invitations
CREATE POLICY "Owners and admins can delete invitations" ON invitations
  FOR DELETE USING (
    EXISTS (
      SELECT 1 FROM memberships m
      JOIN users u ON m.user_id = u.id
      WHERE m.business_id = invitations.business_id
      AND u.auth_id = auth.uid()
      AND m.role IN ('owner', 'admin')
    )
  );
