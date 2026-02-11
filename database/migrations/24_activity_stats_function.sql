-- Activity stats aggregate function for dashboard
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
$$ LANGUAGE plpgsql STABLE;
