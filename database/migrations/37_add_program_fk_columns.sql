-- Migration 37: Add program_id / enrollment_id FK columns to existing tables
-- Phase 3 of the migration strategy.

-- ============================================
-- 1. card_designs: Add program_id FK
-- ============================================

ALTER TABLE card_designs
ADD COLUMN IF NOT EXISTS program_id UUID REFERENCES loyalty_programs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_card_designs_program
ON card_designs(program_id);

COMMENT ON COLUMN card_designs.total_stamps IS
    'DEPRECATED: Use loyalty_programs.config.total_stamps instead. Kept for backward compatibility.';

COMMENT ON COLUMN card_designs.back_fields IS
    'DEPRECATED: Use loyalty_programs.back_fields instead. Kept for backward compatibility.';

-- ============================================
-- 2. transactions: Add program_id and enrollment_id FKs
-- ============================================

ALTER TABLE transactions
ADD COLUMN IF NOT EXISTS program_id UUID REFERENCES loyalty_programs(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS enrollment_id UUID REFERENCES enrollments(id) ON DELETE SET NULL;

-- Expand type CHECK to include new transaction types
ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_type_check;
ALTER TABLE transactions ADD CONSTRAINT transactions_type_check
CHECK (type IN (
    'stamp_added', 'reward_redeemed', 'stamp_voided', 'bonus_stamp', 'stamps_adjusted',
    'points_earned', 'points_redeemed', 'points_expired', 'points_adjusted',
    'tier_upgraded', 'tier_downgraded'
));

CREATE INDEX IF NOT EXISTS idx_transactions_program
ON transactions(program_id);

CREATE INDEX IF NOT EXISTS idx_transactions_enrollment
ON transactions(enrollment_id);

-- ============================================
-- 3. push_registrations: Add enrollment_id FK
-- ============================================

ALTER TABLE push_registrations
ADD COLUMN IF NOT EXISTS enrollment_id UUID REFERENCES enrollments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_push_registrations_enrollment
ON push_registrations(enrollment_id);
