-- Migration 31: Create notification_templates table
-- Per-program notification configuration. System seeds defaults; Pro users customize.

CREATE TABLE IF NOT EXISTS notification_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID NOT NULL REFERENCES loyalty_programs(id) ON DELETE CASCADE,
    trigger TEXT NOT NULL CHECK (trigger IN (
        'stamp_added', 'reward_earned', 'reward_redeemed',
        'milestone', 'inactivity', 'welcome',
        'tier_upgrade', 'tier_downgrade', 'points_expiring'
    )),
    trigger_config JSONB DEFAULT '{}',
    title_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    translations JSONB DEFAULT '{}',
    is_default BOOLEAN NOT NULL DEFAULT false,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    is_customized BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_templates_program
ON notification_templates(program_id);

CREATE INDEX IF NOT EXISTS idx_notification_templates_trigger
ON notification_templates(program_id, trigger) WHERE is_enabled = true;

-- RLS
ALTER TABLE notification_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage notification_templates"
ON notification_templates FOR ALL
USING ((SELECT auth.role()) = 'service_role');

-- Updated_at trigger
CREATE TRIGGER update_notification_templates_updated_at
    BEFORE UPDATE ON notification_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
