-- Add business status for early access / invite-only model
-- Businesses start as 'pending' and require admin activation

ALTER TABLE businesses
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'
  CHECK (status IN ('pending', 'active', 'suspended'));

ALTER TABLE businesses
  ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ;

-- Existing businesses become active
UPDATE businesses SET status = 'active', activated_at = NOW() WHERE status = 'pending';

-- Enable realtime for status change subscriptions
ALTER PUBLICATION supabase_realtime ADD TABLE businesses;
