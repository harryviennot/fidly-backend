SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    stamps INTEGER DEFAULT 0 CHECK (stamps >= 0 AND stamps <= 10),
    auth_token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS push_registrations (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    device_library_id TEXT NOT NULL,
    push_token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    UNIQUE(customer_id, device_library_id)
);

CREATE INDEX IF NOT EXISTS idx_push_customer ON push_registrations(customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_email ON customers(email);

CREATE TABLE IF NOT EXISTS card_designs (
    id TEXT PRIMARY KEY,
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
    secondary_fields TEXT DEFAULT '[]',
    auxiliary_fields TEXT DEFAULT '[]',
    back_fields TEXT DEFAULT '[]',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_card_designs_active ON card_designs(is_active);
"""
