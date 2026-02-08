-- Demo system tables for interactive landing page demo
-- Completely isolated from business tables to protect Apple reputation
-- Sessions auto-expire after 24 hours

-- ============================================
-- DEMO SESSIONS (Links browser to phone)
-- ============================================

CREATE TABLE demo_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token TEXT UNIQUE NOT NULL,
    demo_customer_id UUID,  -- Set when pass is downloaded
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'pass_downloaded', 'pass_installed')),
    stamps INTEGER DEFAULT 0 CHECK (stamps >= 0 AND stamps <= 8),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE UNIQUE INDEX idx_demo_sessions_token ON demo_sessions(session_token);
CREATE INDEX idx_demo_sessions_status ON demo_sessions(status);
CREATE INDEX idx_demo_sessions_expires ON demo_sessions(expires_at);

CREATE TRIGGER update_demo_sessions_updated_at
    BEFORE UPDATE ON demo_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE demo_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to demo_sessions" ON demo_sessions FOR ALL USING (true);

-- ============================================
-- DEMO CUSTOMERS (Minimal record for demo passes)
-- ============================================

CREATE TABLE demo_customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES demo_sessions(id) ON DELETE CASCADE,
    auth_token TEXT NOT NULL,  -- For Apple Wallet authentication
    stamps INTEGER DEFAULT 0 CHECK (stamps >= 0 AND stamps <= 8),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_demo_customers_session ON demo_customers(session_id);

CREATE TRIGGER update_demo_customers_updated_at
    BEFORE UPDATE ON demo_customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE demo_customers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to demo_customers" ON demo_customers FOR ALL USING (true);

-- Add foreign key from sessions to customers (after customers table exists)
ALTER TABLE demo_sessions
ADD CONSTRAINT demo_sessions_customer_fkey
FOREIGN KEY (demo_customer_id) REFERENCES demo_customers(id) ON DELETE SET NULL;

-- ============================================
-- DEMO PUSH REGISTRATIONS (Device tokens)
-- ============================================

CREATE TABLE demo_push_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    demo_customer_id UUID NOT NULL REFERENCES demo_customers(id) ON DELETE CASCADE,
    device_library_id TEXT NOT NULL,
    push_token TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(demo_customer_id, device_library_id)
);

CREATE INDEX idx_demo_push_customer ON demo_push_registrations(demo_customer_id);

ALTER TABLE demo_push_registrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to demo_push_registrations" ON demo_push_registrations FOR ALL USING (true);
