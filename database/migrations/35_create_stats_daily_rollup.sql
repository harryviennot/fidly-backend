-- Migration 35: Create stats_daily_rollup table
-- Pre-aggregated daily analytics per program.

CREATE TABLE IF NOT EXISTS stats_daily_rollup (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    program_id UUID REFERENCES loyalty_programs(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    stamps_added INT DEFAULT 0,
    rewards_redeemed INT DEFAULT 0,
    points_earned INT DEFAULT 0,
    points_redeemed INT DEFAULT 0,
    new_customers INT DEFAULT 0,
    active_customers INT DEFAULT 0,
    returning_customers INT DEFAULT 0,
    programs_completed INT DEFAULT 0,
    hourly_activity JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(business_id, program_id, date)
);

CREATE INDEX IF NOT EXISTS idx_stats_rollup_business_date
ON stats_daily_rollup(business_id, date);

CREATE INDEX IF NOT EXISTS idx_stats_rollup_program_date
ON stats_daily_rollup(program_id, date);

ALTER TABLE stats_daily_rollup ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage stats_daily_rollup"
ON stats_daily_rollup FOR ALL
USING ((SELECT auth.role()) = 'service_role');
