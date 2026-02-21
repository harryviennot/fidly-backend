-- Migration 33: Create design_schedules table
-- Scheduled design changes (holiday themes, promotions).

CREATE TABLE IF NOT EXISTS design_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    design_id UUID NOT NULL REFERENCES card_designs(id) ON DELETE CASCADE,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ,
    is_revert BOOLEAN NOT NULL DEFAULT false,
    revert_to_design_id UUID REFERENCES card_designs(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'active', 'completed', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_design_schedules_business
ON design_schedules(business_id);

CREATE INDEX IF NOT EXISTS idx_design_schedules_pending
ON design_schedules(starts_at) WHERE status = 'scheduled';

ALTER TABLE design_schedules ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage design_schedules"
ON design_schedules FOR ALL
USING ((SELECT auth.role()) = 'service_role');

CREATE TRIGGER update_design_schedules_updated_at
    BEFORE UPDATE ON design_schedules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
