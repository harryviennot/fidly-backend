-- ============================================
-- ONBOARDING STORAGE BUCKET
-- ============================================
-- Stores logo uploads during onboarding
-- Path structure: {user_id}/logo.png

-- Create bucket with PNG-only restriction
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('onboarding', 'onboarding', true, 2097152, ARRAY['image/png'])
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- RLS POLICIES
-- ============================================

-- Users can upload to their own folder
CREATE POLICY "upload_own_onboarding" ON storage.objects
FOR INSERT WITH CHECK (
  bucket_id = 'onboarding' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Users can delete from their own folder
CREATE POLICY "delete_own_onboarding" ON storage.objects
FOR DELETE USING (
  bucket_id = 'onboarding' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Users can update their own files (for re-upload)
CREATE POLICY "update_own_onboarding" ON storage.objects
FOR UPDATE USING (
  bucket_id = 'onboarding' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Public read for onboarding assets (needed for preview)
CREATE POLICY "public_read_onboarding" ON storage.objects
FOR SELECT USING (bucket_id = 'onboarding');
