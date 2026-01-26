-- Multi-tenant business system setup
-- Creates businesses, users, memberships tables
-- Updates customers, card_designs, push_registrations with business_id scoping

-- ============================================
-- Helper function for auto-updating timestamps
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- BUSINESSES (Tenants)
-- ============================================

CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    url_slug TEXT UNIQUE NOT NULL,
    subscription_tier TEXT NOT NULL DEFAULT 'pay' CHECK (subscription_tier IN ('pay', 'pro')),
    stripe_customer_id TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_businesses_url_slug ON businesses(url_slug);
CREATE INDEX idx_businesses_stripe_customer ON businesses(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

CREATE TRIGGER update_businesses_updated_at
    BEFORE UPDATE ON businesses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE businesses ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to businesses" ON businesses FOR ALL USING (true);

-- ============================================
-- USERS (Platform users - NOT customers)
-- ============================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_users_email ON users(email);

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to users" ON users FOR ALL USING (true);

-- ============================================
-- MEMBERSHIPS (Links users to businesses)
-- ============================================

CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'scanner' CHECK (role IN ('owner', 'scanner')),
    invited_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, business_id)
);

CREATE INDEX idx_memberships_user ON memberships(user_id);
CREATE INDEX idx_memberships_business ON memberships(business_id);
CREATE INDEX idx_memberships_role ON memberships(role);

CREATE TRIGGER update_memberships_updated_at
    BEFORE UPDATE ON memberships
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to memberships" ON memberships FOR ALL USING (true);

-- ============================================
-- CUSTOMERS (Loyalty card holders per business)
-- ============================================

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    stamps INTEGER DEFAULT 0 CHECK (stamps >= 0),
    auth_token TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(business_id, email)
);

CREATE INDEX idx_customers_business ON customers(business_id);
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_business_email ON customers(business_id, email);

CREATE TRIGGER update_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to customers" ON customers FOR ALL USING (true);

-- ============================================
-- CARD DESIGNS (Per business)
-- ============================================

CREATE TABLE card_designs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,

    -- Pass Colors
    foreground_color TEXT DEFAULT 'rgb(255, 255, 255)',
    background_color TEXT DEFAULT 'rgb(139, 90, 43)',
    label_color TEXT DEFAULT 'rgb(255, 255, 255)',

    -- Text Fields
    organization_name TEXT NOT NULL,
    description TEXT NOT NULL,
    logo_text TEXT,

    -- Stamp Configuration
    total_stamps INTEGER DEFAULT 10 CHECK (total_stamps >= 1 AND total_stamps <= 20),
    stamp_filled_color TEXT DEFAULT 'rgb(255, 215, 0)',
    stamp_empty_color TEXT DEFAULT 'rgb(80, 50, 20)',
    stamp_border_color TEXT DEFAULT 'rgb(255, 255, 255)',

    -- Custom Assets (file paths relative to uploads/)
    logo_path TEXT,
    custom_filled_stamp_path TEXT,
    custom_empty_stamp_path TEXT,

    -- Pass Fields (JSON arrays of {key, label, value})
    secondary_fields JSONB DEFAULT '[]',
    auxiliary_fields JSONB DEFAULT '[]',
    back_fields JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_card_designs_business ON card_designs(business_id);
CREATE INDEX idx_card_designs_active ON card_designs(business_id, is_active) WHERE is_active = true;

-- Ensure only one active design per business
CREATE UNIQUE INDEX idx_one_active_design_per_business
    ON card_designs(business_id)
    WHERE is_active = true;

CREATE TRIGGER update_card_designs_updated_at
    BEFORE UPDATE ON card_designs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE card_designs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to card_designs" ON card_designs FOR ALL USING (true);

-- ============================================
-- PUSH REGISTRATIONS (Device tokens for pass updates)
-- ============================================

CREATE TABLE push_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    device_library_id TEXT NOT NULL,
    push_token TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(customer_id, device_library_id)
);

CREATE INDEX idx_push_customer ON push_registrations(customer_id);
CREATE INDEX idx_push_device ON push_registrations(device_library_id);

ALTER TABLE push_registrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to push_registrations" ON push_registrations FOR ALL USING (true);
