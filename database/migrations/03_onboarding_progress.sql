-- Onboarding Progress Table
-- Stores draft onboarding data so users can resume across sessions/devices

-- ============================================
-- CREATE ONBOARDING_PROGRESS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS onboarding_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    business_name TEXT NOT NULL,
    url_slug TEXT NOT NULL,
    owner_name TEXT,
    category TEXT,
    description TEXT,
    email TEXT,
    card_design JSONB,
    current_step INTEGER NOT NULL DEFAULT 1 CHECK (current_step >= 1 AND current_step <= 6),
    completed_steps INTEGER[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast lookups by user_id (already unique, but explicit for clarity)
CREATE INDEX IF NOT EXISTS idx_onboarding_progress_user_id ON onboarding_progress(user_id);

-- ============================================
-- AUTO-UPDATE updated_at TRIGGER
-- ============================================

CREATE OR REPLACE FUNCTION update_onboarding_progress_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS onboarding_progress_updated_at ON onboarding_progress;
CREATE TRIGGER onboarding_progress_updated_at
    BEFORE UPDATE ON onboarding_progress
    FOR EACH ROW
    EXECUTE FUNCTION update_onboarding_progress_updated_at();

-- ============================================
-- ENABLE RLS
-- ============================================

ALTER TABLE onboarding_progress ENABLE ROW LEVEL SECURITY;

-- ============================================
-- RLS POLICIES
-- ============================================

-- Users can view their own onboarding progress
CREATE POLICY "Users can view own onboarding progress" ON onboarding_progress
    FOR SELECT
    USING (user_id = public.get_user_id());

-- Users can insert their own onboarding progress
CREATE POLICY "Users can create own onboarding progress" ON onboarding_progress
    FOR INSERT
    WITH CHECK (user_id = public.get_user_id());

-- Users can update their own onboarding progress
CREATE POLICY "Users can update own onboarding progress" ON onboarding_progress
    FOR UPDATE
    USING (user_id = public.get_user_id())
    WITH CHECK (user_id = public.get_user_id());

-- Users can delete their own onboarding progress
CREATE POLICY "Users can delete own onboarding progress" ON onboarding_progress
    FOR DELETE
    USING (user_id = public.get_user_id());

-- Service role full access (for backend operations)
CREATE POLICY "Service role full access to onboarding_progress" ON onboarding_progress
    FOR ALL
    USING (auth.role() = 'service_role');
