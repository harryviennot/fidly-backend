-- Backfill default customer_data_collection settings for existing businesses
UPDATE businesses
SET settings = jsonb_set(
  COALESCE(settings, '{}'::jsonb),
  '{customer_data_collection}',
  '{"collect_name": true, "collect_email": true, "collect_phone": false}'::jsonb
)
WHERE settings IS NULL
   OR NOT settings ? 'customer_data_collection';
