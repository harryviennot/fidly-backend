-- Add total_redemptions counter to customers
ALTER TABLE customers ADD COLUMN IF NOT EXISTS total_redemptions INTEGER NOT NULL DEFAULT 0;

-- Transactions audit log
CREATE TABLE IF NOT EXISTS transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  employee_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  type TEXT NOT NULL CHECK (type IN (
    'stamp_added', 'reward_redeemed', 'stamp_voided', 'bonus_stamp', 'stamps_adjusted'
  )),
  stamp_delta INTEGER NOT NULL DEFAULT 0,
  stamps_before INTEGER NOT NULL,
  stamps_after INTEGER NOT NULL,
  metadata JSONB DEFAULT '{}',
  source TEXT NOT NULL DEFAULT 'scanner' CHECK (source IN ('scanner', 'dashboard', 'api', 'system')),
  voided_transaction_id UUID REFERENCES transactions(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_transactions_business ON transactions (business_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_customer ON transactions (customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions (business_id, type, created_at DESC);

-- Prevent double-void at DB level
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_unique_void
  ON transactions (voided_transaction_id)
  WHERE voided_transaction_id IS NOT NULL AND type = 'stamp_voided';

ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
