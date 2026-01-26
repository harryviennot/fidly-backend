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
"""
