-- Migration 36: Create offline_queue table
-- For scanner app offline support.

CREATE TABLE IF NOT EXISTS offline_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT NOT NULL UNIQUE,
    scanner_user_id UUID NOT NULL REFERENCES users(id),
    business_id UUID NOT NULL REFERENCES businesses(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    program_id UUID REFERENCES loyalty_programs(id),
    action TEXT NOT NULL CHECK (action IN ('stamp', 'redeem', 'void')),
    payload JSONB DEFAULT '{}',
    created_offline_at TIMESTAMPTZ NOT NULL,
    synced_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'synced', 'failed', 'conflict')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_offline_queue_business
ON offline_queue(business_id) WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_offline_queue_client_id
ON offline_queue(client_id);

ALTER TABLE offline_queue ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage offline_queue"
ON offline_queue FOR ALL
USING ((SELECT auth.role()) = 'service_role');
