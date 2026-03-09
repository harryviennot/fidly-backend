-- Migration 38: Data migration - populate programs and enrollments from existing data
-- Phase 2 of the migration strategy. INSERT-only, no destructive changes.

-- ============================================
-- 1. Create default loyalty_program for each business with an active design
-- ============================================

INSERT INTO loyalty_programs (business_id, name, type, is_active, is_default, config, reward_name, back_fields, translations)
SELECT
    cd.business_id,
    COALESCE(cd.name, 'Programme de fidelite'),
    'stamp',
    true,
    true,
    jsonb_build_object(
        'total_stamps', COALESCE(cd.total_stamps, 10),
        'auto_reset_on_redeem', true
    ),
    NULL,
    COALESCE(cd.back_fields, '[]'::jsonb),
    COALESCE(cd.translations, '{}'::jsonb)
FROM card_designs cd
WHERE cd.is_active = true
ON CONFLICT DO NOTHING;

-- Also create programs for businesses that have designs but none active
INSERT INTO loyalty_programs (business_id, name, type, is_active, is_default, config, back_fields, translations)
SELECT DISTINCT ON (cd.business_id)
    cd.business_id,
    COALESCE(cd.name, 'Programme de fidelite'),
    'stamp',
    false,
    true,
    jsonb_build_object(
        'total_stamps', COALESCE(cd.total_stamps, 10),
        'auto_reset_on_redeem', true
    ),
    COALESCE(cd.back_fields, '[]'::jsonb),
    COALESCE(cd.translations, '{}'::jsonb)
FROM card_designs cd
WHERE NOT EXISTS (
    SELECT 1 FROM loyalty_programs lp WHERE lp.business_id = cd.business_id
)
ORDER BY cd.business_id, cd.created_at DESC
ON CONFLICT DO NOTHING;

-- ============================================
-- 2. Link card_designs to their programs
-- ============================================

UPDATE card_designs cd
SET program_id = lp.id
FROM loyalty_programs lp
WHERE lp.business_id = cd.business_id
AND lp.is_default = true
AND cd.program_id IS NULL;

-- ============================================
-- 3. Create enrollments from existing customers
-- ============================================

INSERT INTO enrollments (customer_id, program_id, progress, status, total_redemptions, enrolled_at, last_activity_at)
SELECT
    c.id,
    lp.id,
    jsonb_build_object('stamps', COALESCE(c.stamps, 0)),
    'active',
    COALESCE(c.total_redemptions, 0),
    c.created_at,
    c.updated_at
FROM customers c
JOIN loyalty_programs lp ON lp.business_id = c.business_id AND lp.is_default = true
ON CONFLICT (customer_id, program_id) DO NOTHING;

-- ============================================
-- 4. Backfill transactions with program_id and enrollment_id
-- ============================================

UPDATE transactions t
SET
    program_id = lp.id,
    enrollment_id = e.id
FROM loyalty_programs lp
JOIN enrollments e ON e.program_id = lp.id
WHERE lp.business_id = t.business_id
AND lp.is_default = true
AND e.customer_id = t.customer_id
AND t.program_id IS NULL;

-- ============================================
-- 5. Link push_registrations to enrollments
-- ============================================

UPDATE push_registrations pr
SET enrollment_id = e.id
FROM enrollments e
JOIN loyalty_programs lp ON lp.id = e.program_id
JOIN customers c ON c.id = e.customer_id
WHERE e.customer_id = pr.customer_id
AND lp.business_id = c.business_id
AND lp.is_default = true
AND pr.enrollment_id IS NULL;

-- ============================================
-- 6. Seed default notification templates for each program
-- ============================================

INSERT INTO notification_templates (program_id, trigger, title_template, body_template, is_default, is_enabled)
SELECT
    lp.id,
    t.trigger,
    t.title_template,
    t.body_template,
    true,
    true
FROM loyalty_programs lp
CROSS JOIN (VALUES
    ('stamp_added', 'Stamp Added!', 'You now have {{stamps}}/{{total_stamps}} stamps.'),
    ('reward_earned', 'Reward Earned!', 'Congratulations! You''ve earned {{reward_name}}!'),
    ('reward_redeemed', 'Reward Redeemed', 'Your reward has been redeemed. Card reset to 0.'),
    ('welcome', 'Welcome!', 'Welcome to our loyalty program!')
) AS t(trigger, title_template, body_template)
ON CONFLICT DO NOTHING;
