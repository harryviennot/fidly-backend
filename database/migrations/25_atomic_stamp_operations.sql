-- Atomic stamp operations to prevent race conditions on concurrent scans.
-- These RPC functions replace read-then-write patterns in the backend.

-- Atomic stamp increment (returns new count)
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
$$ LANGUAGE plpgsql;

-- Atomic stamp decrement (returns new count, min 0)
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
$$ LANGUAGE plpgsql;

-- Atomic redemption increment
CREATE OR REPLACE FUNCTION increment_redemptions(p_customer_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE customers
    SET total_redemptions = total_redemptions + 1, updated_at = NOW()
    WHERE id = p_customer_id;
END;
$$ LANGUAGE plpgsql;
