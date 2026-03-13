-- Migration: Convert data collection settings from boolean to tri-state ("off" | "required" | "optional")
-- This allows business owners to make fields optional instead of always required when enabled.

UPDATE businesses
SET settings = jsonb_set(
  settings,
  '{customer_data_collection}',
  jsonb_build_object(
    'collect_name',
    CASE
      WHEN (settings->'customer_data_collection'->>'collect_name')::text = 'true' THEN 'required'
      ELSE 'off'
    END,
    'collect_email',
    CASE
      WHEN (settings->'customer_data_collection'->>'collect_email')::text = 'true' THEN 'required'
      ELSE 'off'
    END,
    'collect_phone',
    CASE
      WHEN (settings->'customer_data_collection'->>'collect_phone')::text = 'true' THEN 'required'
      ELSE 'off'
    END
  )
)
WHERE settings ? 'customer_data_collection'
  AND jsonb_typeof(settings->'customer_data_collection'->'collect_name') = 'boolean';
