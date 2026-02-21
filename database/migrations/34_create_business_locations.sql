-- Migration 34: Create business_locations table
-- For Apple/Google Wallet geofencing (Pro feature).

CREATE TABLE IF NOT EXISTS business_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    address TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    radius_meters INT DEFAULT 100,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_business_locations_business
ON business_locations(business_id);

ALTER TABLE business_locations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage business_locations"
ON business_locations FOR ALL
USING ((SELECT auth.role()) = 'service_role');

CREATE TRIGGER update_business_locations_updated_at
    BEFORE UPDATE ON business_locations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
