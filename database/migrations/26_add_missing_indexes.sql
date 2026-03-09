-- Add indexes on frequently queried columns for performance.

-- auth_token lookup (used by every Apple Wallet callback)
CREATE INDEX IF NOT EXISTS idx_customers_auth_token ON customers(auth_token);

-- business status filtering (admin panel queries)
CREATE INDEX IF NOT EXISTS idx_businesses_status ON businesses(status);

-- employee_id on transactions (for employee activity reports)
CREATE INDEX IF NOT EXISTS idx_transactions_employee ON transactions(employee_id) WHERE employee_id IS NOT NULL;

-- invitations invited_by
CREATE INDEX IF NOT EXISTS idx_invitations_invited_by ON invitations(invited_by) WHERE invited_by IS NOT NULL;
