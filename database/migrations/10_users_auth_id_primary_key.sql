-- Migration: Use auth.users.id as users primary key
-- After this migration: users.id = auth.users.id (no separate auth_id column)
--
-- IMPORTANT: This migration is IRREVERSIBLE. Take a full database backup first!
-- STATUS: APPLIED SUCCESSFULLY

-- ============================================
-- Step 1: Store all membership data with email lookup (not user_id)
-- ============================================

-- Create temp table to preserve membership relationships using email
CREATE TEMP TABLE membership_backup AS
SELECT
    m.id,
    u.email as user_email,
    m.business_id,
    m.role,
    inv.email as invited_by_email,
    m.created_at,
    m.updated_at,
    m.last_active_at,
    m.scans_count
FROM memberships m
JOIN users u ON (u.id = m.user_id OR u.auth_id = m.user_id)
LEFT JOIN users inv ON (inv.id = m.invited_by OR inv.auth_id = m.invited_by);

-- Store onboarding progress
CREATE TEMP TABLE onboarding_backup AS
SELECT
    op.id,
    u.email as user_email,
    op.business_name,
    op.url_slug,
    op.owner_name,
    op.category,
    op.description,
    op.email as onboarding_email,
    op.card_design,
    op.current_step,
    op.completed_steps,
    op.created_at,
    op.updated_at
FROM onboarding_progress op
JOIN users u ON (u.id = op.user_id OR u.auth_id = op.user_id);

-- Store invitations
CREATE TEMP TABLE invitations_backup AS
SELECT
    i.id,
    i.business_id,
    i.email,
    i.name,
    i.role,
    i.token,
    inv.email as invited_by_email,
    i.status,
    i.expires_at,
    i.created_at,
    i.accepted_at
FROM invitations i
JOIN users inv ON (inv.id = i.invited_by OR inv.auth_id = i.invited_by);

-- ============================================
-- Step 2: Drop RLS policies that depend on auth_id FIRST
-- ============================================

DROP POLICY IF EXISTS "Users can view own profile" ON users;
DROP POLICY IF EXISTS "Users can update own profile" ON users;
DROP POLICY IF EXISTS "Users can view business invitations" ON invitations;
DROP POLICY IF EXISTS "Owners and admins can create invitations" ON invitations;
DROP POLICY IF EXISTS "Owners and admins can update invitations" ON invitations;
DROP POLICY IF EXISTS "Owners and admins can delete invitations" ON invitations;

-- ============================================
-- Step 3: Drop all foreign key constraints
-- ============================================

ALTER TABLE memberships DROP CONSTRAINT IF EXISTS memberships_user_id_fkey;
ALTER TABLE memberships DROP CONSTRAINT IF EXISTS memberships_invited_by_fkey;
ALTER TABLE invitations DROP CONSTRAINT IF EXISTS invitations_invited_by_fkey;
ALTER TABLE onboarding_progress DROP CONSTRAINT IF EXISTS onboarding_progress_user_id_fkey;

-- ============================================
-- Step 4: Clear dependent tables
-- ============================================

DELETE FROM memberships;
DELETE FROM invitations;
DELETE FROM onboarding_progress;

-- ============================================
-- Step 5: Modify users table
-- ============================================

-- Delete users without auth_id (can't be migrated)
DELETE FROM users WHERE auth_id IS NULL;

-- Drop the old primary key
ALTER TABLE users DROP CONSTRAINT users_pkey;

-- Drop the auth_id unique constraint and index
DROP INDEX IF EXISTS idx_users_auth_id;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_auth_id_key;

-- Update the id column with auth_id values
UPDATE users SET id = auth_id;

-- Add new primary key
ALTER TABLE users ADD PRIMARY KEY (id);

-- Drop the auth_id column (now redundant)
ALTER TABLE users DROP COLUMN auth_id;

-- ============================================
-- Step 6: Restore dependent data with new user IDs
-- ============================================

-- Restore memberships
INSERT INTO memberships (id, user_id, business_id, role, invited_by, created_at, updated_at, last_active_at, scans_count)
SELECT
    mb.id,
    u.id as user_id,
    mb.business_id,
    mb.role,
    inv.id as invited_by,
    mb.created_at,
    mb.updated_at,
    mb.last_active_at,
    mb.scans_count
FROM membership_backup mb
JOIN users u ON u.email = mb.user_email
LEFT JOIN users inv ON inv.email = mb.invited_by_email;

-- Restore onboarding progress
INSERT INTO onboarding_progress (id, user_id, business_name, url_slug, owner_name, category, description, email, card_design, current_step, completed_steps, created_at, updated_at)
SELECT
    ob.id,
    u.id as user_id,
    ob.business_name,
    ob.url_slug,
    ob.owner_name,
    ob.category,
    ob.description,
    ob.onboarding_email,
    ob.card_design,
    ob.current_step,
    ob.completed_steps,
    ob.created_at,
    ob.updated_at
FROM onboarding_backup ob
JOIN users u ON u.email = ob.user_email;

-- Restore invitations
INSERT INTO invitations (id, business_id, email, name, role, token, invited_by, status, expires_at, created_at, accepted_at)
SELECT
    ib.id,
    ib.business_id,
    ib.email,
    ib.name,
    ib.role,
    ib.token,
    inv.id as invited_by,
    ib.status,
    ib.expires_at,
    ib.created_at,
    ib.accepted_at
FROM invitations_backup ib
JOIN users inv ON inv.email = ib.invited_by_email;

-- ============================================
-- Step 7: Recreate foreign key constraints
-- ============================================

ALTER TABLE memberships
ADD CONSTRAINT memberships_user_id_fkey
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE memberships
ADD CONSTRAINT memberships_invited_by_fkey
FOREIGN KEY (invited_by) REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE invitations
ADD CONSTRAINT invitations_invited_by_fkey
FOREIGN KEY (invited_by) REFERENCES users(id);

ALTER TABLE onboarding_progress
ADD CONSTRAINT onboarding_progress_user_id_fkey
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- ============================================
-- Step 8: Update trigger to use auth id directly
-- ============================================

CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (id, email, name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1))
    )
    ON CONFLICT (email) DO UPDATE SET
        updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- Step 9: Update helper functions
-- ============================================

CREATE OR REPLACE FUNCTION public.get_user_id()
RETURNS UUID AS $$
    SELECT auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

-- ============================================
-- Step 10: Recreate RLS policies with new logic (id = auth.uid())
-- ============================================

CREATE POLICY "Users can view own profile" ON users
    FOR SELECT
    USING (id = auth.uid());

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

CREATE POLICY "Users can view business invitations" ON invitations
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM memberships m
      JOIN users u ON m.user_id = u.id
      WHERE m.business_id = invitations.business_id
      AND u.id = auth.uid()
      AND m.role IN ('owner', 'admin')
    )
  );

CREATE POLICY "Owners and admins can create invitations" ON invitations
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM memberships m
      JOIN users u ON m.user_id = u.id
      WHERE m.business_id = invitations.business_id
      AND u.id = auth.uid()
      AND m.role IN ('owner', 'admin')
    )
  );

CREATE POLICY "Owners and admins can update invitations" ON invitations
  FOR UPDATE USING (
    EXISTS (
      SELECT 1 FROM memberships m
      JOIN users u ON m.user_id = u.id
      WHERE m.business_id = invitations.business_id
      AND u.id = auth.uid()
      AND m.role IN ('owner', 'admin')
    )
  );

CREATE POLICY "Owners and admins can delete invitations" ON invitations
  FOR DELETE USING (
    EXISTS (
      SELECT 1 FROM memberships m
      JOIN users u ON m.user_id = u.id
      WHERE m.business_id = invitations.business_id
      AND u.id = auth.uid()
      AND m.role IN ('owner', 'admin')
    )
  );

-- ============================================
-- Step 11: Clean up temp tables
-- ============================================

DROP TABLE membership_backup;
DROP TABLE onboarding_backup;
DROP TABLE invitations_backup;
