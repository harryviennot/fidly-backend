-- Tighten RLS policies to close security gaps exposed via anon key.
-- Backend uses service_role (bypasses RLS). These policies only affect
-- direct PostgREST/JS-client access with anon or authenticated JWTs.

-- ============================================
-- CUSTOMERS: Remove overly broad anon SELECT
-- ============================================
-- The "Anonymous can read own customer by token" policy currently allows
-- anon to read ALL customers. Backend handles all customer queries via
-- service_role, so we drop the anon policy entirely.
DROP POLICY IF EXISTS "Anonymous can read own customer by token" ON customers;

-- ============================================
-- PUSH_REGISTRATIONS: Remove overly broad anon FOR ALL
-- ============================================
-- The "Anonymous can manage push registrations" policy currently gives
-- full anon CRUD on all push registrations. Backend handles all push
-- registration via service_role Apple Wallet callbacks.
DROP POLICY IF EXISTS "Anonymous can manage push registrations" ON push_registrations;

-- ============================================
-- INVITATIONS: Replace wide-open SELECT
-- ============================================
-- The "Anyone can view invitation by token" policy uses USING(true),
-- allowing enumeration of all invitations via anon key.
-- Replace with authenticated-only: users can see invitations sent to their email.
DROP POLICY IF EXISTS "Anyone can view invitation by token" ON invitations;

CREATE POLICY "Authenticated users can view own invitations" ON invitations
  FOR SELECT USING (
    auth.role() = 'authenticated'
    AND email = (SELECT email FROM auth.users WHERE id = auth.uid())
  );

-- ============================================
-- MEMBERSHIPS: Tighten SELECT to own rows only
-- ============================================
-- Current policy allows members to see ALL memberships for their business.
-- Frontend only needs the user's own memberships (business-context.tsx).
-- Drop the broad policy and replace with user-scoped one.
DROP POLICY IF EXISTS "Members can view business memberships" ON memberships;

CREATE POLICY "Users can view own memberships" ON memberships
  FOR SELECT USING (user_id = auth.uid());
