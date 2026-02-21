-- Migration 29: Create loyalty_programs table
-- Central entity for the programs-vs-designs decoupling.
-- Each business can have multiple programs; one marked as default.

CREATE TABLE IF NOT EXISTS loyalty_programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('stamp', 'points', 'tiered')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_default BOOLEAN NOT NULL DEFAULT false,
    config JSONB NOT NULL DEFAULT '{}',
    reward_name TEXT,
    reward_description TEXT,
    back_fields JSONB DEFAULT '[]',
    translations JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Only one default program per business
CREATE UNIQUE INDEX IF NOT EXISTS idx_loyalty_programs_default
ON loyalty_programs(business_id) WHERE is_default = true;

CREATE INDEX IF NOT EXISTS idx_loyalty_programs_business
ON loyalty_programs(business_id);

CREATE INDEX IF NOT EXISTS idx_loyalty_programs_business_active
ON loyalty_programs(business_id) WHERE is_active = true;

-- RLS
ALTER TABLE loyalty_programs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage loyalty_programs"
ON loyalty_programs FOR ALL
USING ((SELECT auth.role()) = 'service_role');

-- Updated_at trigger
CREATE TRIGGER update_loyalty_programs_updated_at
    BEFORE UPDATE ON loyalty_programs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
