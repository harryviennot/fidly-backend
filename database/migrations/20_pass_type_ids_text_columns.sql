-- Fix: Change encrypted cert columns from BYTEA to TEXT.
-- PostgREST double-encodes BYTEA data, breaking the encrypt/decrypt roundtrip.
-- We store base64-encoded encrypted blobs, which are plain text.

-- Clear any corrupted data from the BYTEA era
DELETE FROM pass_type_ids;

ALTER TABLE pass_type_ids
    ALTER COLUMN signer_cert_encrypted TYPE TEXT,
    ALTER COLUMN signer_key_encrypted TYPE TEXT,
    ALTER COLUMN apns_combined_encrypted TYPE TEXT;
