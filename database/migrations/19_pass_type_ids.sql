-- Per-business Apple Pass Type ID certificates
-- Each business gets its own Pass Type ID from a pre-generated pool

CREATE TABLE IF NOT EXISTS pass_type_ids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier TEXT UNIQUE NOT NULL,        -- e.g. 'pass.com.stampeo.business001'
    team_id TEXT NOT NULL,                   -- Apple Team ID
    signer_cert_encrypted BYTEA NOT NULL,    -- AES-256-GCM encrypted PEM
    signer_key_encrypted BYTEA NOT NULL,
    apns_combined_encrypted BYTEA NOT NULL,
    business_id UUID REFERENCES businesses(id) UNIQUE,
    status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'assigned', 'revoked')),
    assigned_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast pool assignment (find next available)
CREATE INDEX IF NOT EXISTS idx_pass_type_ids_status
    ON pass_type_ids (status)
    WHERE status = 'available';

-- Index for business lookup
CREATE INDEX IF NOT EXISTS idx_pass_type_ids_business_id
    ON pass_type_ids (business_id)
    WHERE business_id IS NOT NULL;

-- Enable RLS (service_role only — no client policies)
ALTER TABLE pass_type_ids ENABLE ROW LEVEL SECURITY;
