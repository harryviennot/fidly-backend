-- Migration 28: Fix Supabase linter warnings
-- 1. Set search_path = '' on all functions to prevent search path injection
-- 2. Tighten RLS on strip_images and google_wallet_notifications

-- ============================================================
-- 1. Re-create all functions with SET search_path = ''
-- ============================================================

-- From migration 25: increment_stamps
CREATE OR REPLACE FUNCTION increment_stamps(p_customer_id UUID, p_max_stamps INTEGER)
RETURNS INTEGER AS $$
DECLARE new_count INTEGER;
BEGIN
    UPDATE customers
    SET stamps = LEAST(stamps + 1, p_max_stamps), updated_at = NOW()
    WHERE id = p_customer_id
    RETURNING stamps INTO new_count;
    RETURN new_count;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- From migration 25: decrement_stamps
CREATE OR REPLACE FUNCTION decrement_stamps(p_customer_id UUID)
RETURNS INTEGER AS $$
DECLARE new_count INTEGER;
BEGIN
    UPDATE customers
    SET stamps = GREATEST(stamps - 1, 0), updated_at = NOW()
    WHERE id = p_customer_id
    RETURNING stamps INTO new_count;
    RETURN new_count;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- From migration 25: increment_redemptions
CREATE OR REPLACE FUNCTION increment_redemptions(p_customer_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE customers
    SET total_redemptions = total_redemptions + 1, updated_at = NOW()
    WHERE id = p_customer_id;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- From migration 24: get_activity_stats
CREATE OR REPLACE FUNCTION get_activity_stats(p_business_id UUID)
RETURNS TABLE (
    stamps_today BIGINT,
    rewards_today BIGINT,
    total_this_week BIGINT,
    active_customers_today BIGINT,
    latest_transaction_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) FILTER (WHERE t.type = 'stamp_added' AND t.created_at >= CURRENT_DATE)::BIGINT AS stamps_today,
        COUNT(*) FILTER (WHERE t.type = 'reward_redeemed' AND t.created_at >= CURRENT_DATE)::BIGINT AS rewards_today,
        COUNT(*) FILTER (WHERE t.created_at >= date_trunc('week', CURRENT_DATE))::BIGINT AS total_this_week,
        COUNT(DISTINCT t.customer_id) FILTER (WHERE t.created_at >= CURRENT_DATE)::BIGINT AS active_customers_today,
        MAX(t.created_at) AS latest_transaction_at
    FROM transactions t
    WHERE t.business_id = p_business_id;
END;
$$ LANGUAGE plpgsql STABLE SET search_path = '';

-- From migration 12: cleanup_old_google_notifications
CREATE OR REPLACE FUNCTION cleanup_old_google_notifications()
RETURNS void AS $$
BEGIN
    DELETE FROM google_wallet_notifications
    WHERE created_at < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- From migration 13: cleanup_old_callback_nonces
CREATE OR REPLACE FUNCTION cleanup_old_callback_nonces()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM google_callback_nonces
    WHERE processed_at < NOW() - INTERVAL '7 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- From migration 01: update_updated_at_column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- From migration 03: update_onboarding_progress_updated_at
CREATE OR REPLACE FUNCTION update_onboarding_progress_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- From migration 10: handle_new_auth_user
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
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- From migration 10: get_user_id
CREATE OR REPLACE FUNCTION public.get_user_id()
RETURNS UUID AS $$
    SELECT auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER STABLE SET search_path = '';

-- From migration 02: user_has_business_access
CREATE OR REPLACE FUNCTION public.user_has_business_access(business_uuid UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.memberships
        WHERE user_id = public.get_user_id()
        AND business_id = business_uuid
    )
$$ LANGUAGE SQL SECURITY DEFINER STABLE SET search_path = '';

-- From migration 02: user_is_business_owner
CREATE OR REPLACE FUNCTION public.user_is_business_owner(business_uuid UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.memberships
        WHERE user_id = public.get_user_id()
        AND business_id = business_uuid
        AND role = 'owner'
    )
$$ LANGUAGE SQL SECURITY DEFINER STABLE SET search_path = '';

-- ============================================================
-- 2. Tighten RLS on strip_images and google_wallet_notifications
--    Replace USING (true) with USING (auth.role() = 'service_role')
-- ============================================================

DROP POLICY IF EXISTS "Service role can manage strip_images" ON strip_images;
CREATE POLICY "Service role can manage strip_images"
ON strip_images FOR ALL
USING ((select auth.role()) = 'service_role');

DROP POLICY IF EXISTS "Service role can manage google_wallet_notifications" ON google_wallet_notifications;
CREATE POLICY "Service role can manage google_wallet_notifications"
ON google_wallet_notifications FOR ALL
USING ((select auth.role()) = 'service_role');
