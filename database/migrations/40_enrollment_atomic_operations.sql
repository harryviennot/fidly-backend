-- Atomic decrement for enrollment stamps (replaces broken decrement_stamps RPC on customers table)
CREATE OR REPLACE FUNCTION decrement_enrollment_stamps(p_enrollment_id UUID)
RETURNS INTEGER AS $$
DECLARE new_count INTEGER;
BEGIN
    UPDATE public.enrollments
    SET
        progress = jsonb_set(progress, '{stamps}', to_jsonb(GREATEST((progress->>'stamps')::int - 1, 0))),
        last_activity_at = NOW()
    WHERE id = p_enrollment_id
    RETURNING (progress->>'stamps')::int INTO new_count;
    RETURN new_count;
END;
$$ LANGUAGE plpgsql SET search_path = '';
