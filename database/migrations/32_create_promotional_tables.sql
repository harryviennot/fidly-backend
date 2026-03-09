-- Migration 32: Create promotional_messages and promotional_events tables

-- ============================================
-- 1. PROMOTIONAL MESSAGES (Broadcast notifications - Pro feature)
-- ============================================

CREATE TABLE IF NOT EXISTS promotional_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    target_filter JSONB DEFAULT '{}',
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'scheduled', 'sending', 'sent', 'cancelled')),
    total_recipients INT DEFAULT 0,
    delivered INT DEFAULT 0,
    failed INT DEFAULT 0,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_promotional_messages_business
ON promotional_messages(business_id);

CREATE INDEX IF NOT EXISTS idx_promotional_messages_status
ON promotional_messages(status) WHERE status IN ('scheduled', 'sending');

ALTER TABLE promotional_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage promotional_messages"
ON promotional_messages FOR ALL
USING ((SELECT auth.role()) = 'service_role');

CREATE TRIGGER update_promotional_messages_updated_at
    BEFORE UPDATE ON promotional_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 2. PROMOTIONAL EVENTS (Time-bounded behavior modifiers)
-- ============================================

CREATE TABLE IF NOT EXISTS promotional_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    program_id UUID REFERENCES loyalty_programs(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL CHECK (type IN ('multiplier', 'bonus', 'custom')),
    config JSONB NOT NULL DEFAULT '{}',
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    announcement_title TEXT,
    announcement_body TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CHECK (ends_at > starts_at)
);

CREATE INDEX IF NOT EXISTS idx_promotional_events_business
ON promotional_events(business_id);

CREATE INDEX IF NOT EXISTS idx_promotional_events_active
ON promotional_events(business_id, starts_at, ends_at) WHERE is_active = true;

ALTER TABLE promotional_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage promotional_events"
ON promotional_events FOR ALL
USING ((SELECT auth.role()) = 'service_role');

CREATE TRIGGER update_promotional_events_updated_at
    BEFORE UPDATE ON promotional_events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
