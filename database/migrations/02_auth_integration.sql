-- Auth integration with Supabase Auth
-- Links auth.users to public.users and updates RLS policies

-- ============================================
-- ADD AUTH_ID TO USERS TABLE
-- ============================================

-- Add auth_id column to link with Supabase auth.users
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_id UUID UNIQUE;

-- Create index for fast lookups by auth_id
CREATE INDEX IF NOT EXISTS idx_users_auth_id ON users(auth_id);

-- ============================================
-- AUTO-CREATE PUBLIC USER ON SIGNUP
-- ============================================

-- Function to create a public.users record when auth.users is created
CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (id, auth_id, email, name)
    VALUES (
        gen_random_uuid(),
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1))
    )
    ON CONFLICT (email) DO UPDATE SET
        auth_id = EXCLUDED.auth_id,
        updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger on auth.users insert
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_auth_user();

-- ============================================
-- HELPER FUNCTION: GET USER ID FROM AUTH
-- ============================================

-- Function to get public user id from auth.uid()
CREATE OR REPLACE FUNCTION public.get_user_id()
RETURNS UUID AS $$
    SELECT id FROM public.users WHERE auth_id = auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

-- Function to check if user has membership to a business
CREATE OR REPLACE FUNCTION public.user_has_business_access(business_uuid UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.memberships
        WHERE user_id = public.get_user_id()
        AND business_id = business_uuid
    )
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

-- Function to check if user is owner of a business
CREATE OR REPLACE FUNCTION public.user_is_business_owner(business_uuid UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.memberships
        WHERE user_id = public.get_user_id()
        AND business_id = business_uuid
        AND role = 'owner'
    )
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

-- ============================================
-- UPDATE RLS POLICIES - USERS
-- ============================================

-- Drop existing permissive policy
DROP POLICY IF EXISTS "Allow all access to users" ON users;

-- Users can read their own profile
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT
    USING (auth_id = auth.uid());

-- Users can update their own profile
CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE
    USING (auth_id = auth.uid())
    WITH CHECK (auth_id = auth.uid());

-- Service role can do anything (for triggers and backend)
CREATE POLICY "Service role full access to users" ON users
    FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================
-- UPDATE RLS POLICIES - BUSINESSES
-- ============================================

-- Drop existing permissive policy
DROP POLICY IF EXISTS "Allow all access to businesses" ON businesses;

-- Members can view businesses they belong to
CREATE POLICY "Members can view their businesses" ON businesses
    FOR SELECT
    USING (public.user_has_business_access(id));

-- Owners can update their businesses
CREATE POLICY "Owners can update their businesses" ON businesses
    FOR UPDATE
    USING (public.user_is_business_owner(id))
    WITH CHECK (public.user_is_business_owner(id));

-- Authenticated users can create businesses
CREATE POLICY "Authenticated users can create businesses" ON businesses
    FOR INSERT
    WITH CHECK (auth.role() = 'authenticated');

-- Service role full access
CREATE POLICY "Service role full access to businesses" ON businesses
    FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================
-- UPDATE RLS POLICIES - MEMBERSHIPS
-- ============================================

-- Drop existing permissive policy
DROP POLICY IF EXISTS "Allow all access to memberships" ON memberships;

-- Members can view memberships for businesses they belong to
CREATE POLICY "Members can view business memberships" ON memberships
    FOR SELECT
    USING (public.user_has_business_access(business_id));

-- Owners can insert new memberships (invite employees)
CREATE POLICY "Owners can create memberships" ON memberships
    FOR INSERT
    WITH CHECK (
        public.user_is_business_owner(business_id)
        OR (
            -- Allow self-insertion when creating a new business
            user_id = public.get_user_id()
            AND role = 'owner'
        )
    );

-- Owners can delete memberships (remove employees)
CREATE POLICY "Owners can delete memberships" ON memberships
    FOR DELETE
    USING (
        public.user_is_business_owner(business_id)
        AND user_id != public.get_user_id() -- Cannot remove self
    );

-- Service role full access
CREATE POLICY "Service role full access to memberships" ON memberships
    FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================
-- UPDATE RLS POLICIES - CUSTOMERS
-- ============================================

-- Drop existing permissive policy
DROP POLICY IF EXISTS "Allow all access to customers" ON customers;

-- Members can view customers for their businesses
CREATE POLICY "Members can view business customers" ON customers
    FOR SELECT
    USING (public.user_has_business_access(business_id));

-- Members can create customers (on scan/registration)
CREATE POLICY "Members can create customers" ON customers
    FOR INSERT
    WITH CHECK (public.user_has_business_access(business_id));

-- Members can update customers (add stamps)
CREATE POLICY "Members can update customers" ON customers
    FOR UPDATE
    USING (public.user_has_business_access(business_id))
    WITH CHECK (public.user_has_business_access(business_id));

-- Service role full access (for pass callbacks)
CREATE POLICY "Service role full access to customers" ON customers
    FOR ALL
    USING (auth.role() = 'service_role');

-- Allow anonymous access for customer pass lookups (by auth_token)
CREATE POLICY "Anonymous can read own customer by token" ON customers
    FOR SELECT
    USING (auth.role() = 'anon');

-- ============================================
-- UPDATE RLS POLICIES - CARD_DESIGNS
-- ============================================

-- Drop existing permissive policy
DROP POLICY IF EXISTS "Allow all access to card_designs" ON card_designs;

-- Members can view designs for their businesses
CREATE POLICY "Members can view business designs" ON card_designs
    FOR SELECT
    USING (public.user_has_business_access(business_id));

-- Owners can manage designs
CREATE POLICY "Owners can create designs" ON card_designs
    FOR INSERT
    WITH CHECK (public.user_is_business_owner(business_id));

CREATE POLICY "Owners can update designs" ON card_designs
    FOR UPDATE
    USING (public.user_is_business_owner(business_id))
    WITH CHECK (public.user_is_business_owner(business_id));

CREATE POLICY "Owners can delete designs" ON card_designs
    FOR DELETE
    USING (public.user_is_business_owner(business_id));

-- Service role full access
CREATE POLICY "Service role full access to card_designs" ON card_designs
    FOR ALL
    USING (auth.role() = 'service_role');

-- Anonymous can read active design (for pass generation)
CREATE POLICY "Anonymous can read active designs" ON card_designs
    FOR SELECT
    USING (is_active = true);

-- ============================================
-- UPDATE RLS POLICIES - PUSH_REGISTRATIONS
-- ============================================

-- Drop existing permissive policy
DROP POLICY IF EXISTS "Allow all access to push_registrations" ON push_registrations;

-- Members can view push registrations for their business customers
CREATE POLICY "Members can view push registrations" ON push_registrations
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM customers c
            WHERE c.id = push_registrations.customer_id
            AND public.user_has_business_access(c.business_id)
        )
    );

-- Service role full access (for Apple Wallet callbacks)
CREATE POLICY "Service role full access to push_registrations" ON push_registrations
    FOR ALL
    USING (auth.role() = 'service_role');

-- Anonymous can manage their own push registrations (Apple Wallet callbacks)
CREATE POLICY "Anonymous can manage push registrations" ON push_registrations
    FOR ALL
    USING (auth.role() = 'anon');
