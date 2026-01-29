-- ============================================
-- BUSINESSES STORAGE BUCKET
-- ============================================
-- Stores business assets (logos, etc.)
-- Path structure: {business_id}/logo.png

-- Create bucket with PNG-only restriction
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('businesses', 'businesses', true, 2097152, ARRAY['image/png'])
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- RLS POLICIES
-- ============================================

-- Public read for business assets (logos need to be accessible to all users)
CREATE POLICY "public_read_businesses" ON storage.objects
FOR SELECT USING (bucket_id = 'businesses');

-- Business owners can upload/update/delete their business assets
-- Note: Backend uses service role key, but this allows direct uploads if needed
CREATE POLICY "business_owner_insert" ON storage.objects
FOR INSERT WITH CHECK (
  bucket_id = 'businesses' AND
  EXISTS (
    SELECT 1 FROM memberships m
    WHERE m.business_id::text = (storage.foldername(name))[1]
    AND m.user_id = auth.uid()
    AND m.role = 'owner'
  )
);

CREATE POLICY "business_owner_update" ON storage.objects
FOR UPDATE USING (
  bucket_id = 'businesses' AND
  EXISTS (
    SELECT 1 FROM memberships m
    WHERE m.business_id::text = (storage.foldername(name))[1]
    AND m.user_id = auth.uid()
    AND m.role = 'owner'
  )
);

CREATE POLICY "business_owner_delete" ON storage.objects
FOR DELETE USING (
  bucket_id = 'businesses' AND
  EXISTS (
    SELECT 1 FROM memberships m
    WHERE m.business_id::text = (storage.foldername(name))[1]
    AND m.user_id = auth.uid()
    AND m.role = 'owner'
  )
);
