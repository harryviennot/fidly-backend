-- Migration 29: Fix search_path on functions that use unqualified table names
-- Migration 28 set search_path = '' which broke functions referencing tables
-- without schema qualification. Fix: set search_path = 'public' instead.
-- Functions using fully-qualified public.* names keep search_path = ''.

-- increment_stamps — references: customers
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
$$ LANGUAGE plpgsql SET search_path = 'public';

-- decrement_stamps — references: customers
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
$$ LANGUAGE plpgsql SET search_path = 'public';

-- increment_redemptions — references: customers
CREATE OR REPLACE FUNCTION increment_redemptions(p_customer_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE customers
    SET total_redemptions = total_redemptions + 1, updated_at = NOW()
    WHERE id = p_customer_id;
END;
$$ LANGUAGE plpgsql SET search_path = 'public';

-- get_activity_stats — references: transactions
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
$$ LANGUAGE plpgsql STABLE SET search_path = 'public';

-- cleanup_old_google_notifications — references: google_wallet_notifications
CREATE OR REPLACE FUNCTION cleanup_old_google_notifications()
RETURNS void AS $$
BEGIN
    DELETE FROM google_wallet_notifications
    WHERE created_at < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql SET search_path = 'public';

-- cleanup_old_callback_nonces — references: google_callback_nonces
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
$$ LANGUAGE plpgsql SET search_path = 'public';

-- update_updated_at_column — trigger function (uses NEW, no table refs but fix for consistency)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = 'public';

-- update_onboarding_progress_updated_at — trigger function (same)
CREATE OR REPLACE FUNCTION update_onboarding_progress_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = 'public';
