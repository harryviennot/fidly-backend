-- Migration 30: Create enrollments table
-- Tracks per-customer per-program progress. Replaces customers.stamps.

CREATE TABLE IF NOT EXISTS enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    program_id UUID NOT NULL REFERENCES loyalty_programs(id) ON DELETE CASCADE,
    progress JSONB NOT NULL DEFAULT '{"stamps": 0}',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'paused', 'expired')),
    total_redemptions INT NOT NULL DEFAULT 0,
    last_activity_at TIMESTAMPTZ,
    enrolled_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(customer_id, program_id)
);

CREATE INDEX IF NOT EXISTS idx_enrollments_customer
ON enrollments(customer_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_program
ON enrollments(program_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_program_active
ON enrollments(program_id) WHERE status = 'active';

-- RLS
ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage enrollments"
ON enrollments FOR ALL
USING ((SELECT auth.role()) = 'service_role');
