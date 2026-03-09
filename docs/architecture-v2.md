# Architecture V2: Decoupling Programs from Designs

## Overview

This document describes the v2 data model and service layer that cleanly separates **loyalty program logic** (rules, progress, rewards) from **card design** (visual appearance). This enables:

- Multiple program types (stamps, points, tiered)
- Multiple concurrent programs per business
- Independent design changes without affecting program rules
- Infrastructure for notifications, events, schedules, analytics, and geolocation

---

## 1. Entity-Relationship Diagram

```
                            ┌──────────────┐
                            │  businesses  │
                            └──────┬───────┘
                 ┌─────────┬───────┼─────────┬──────────────┬───────────────┐
                 │         │       │         │              │               │
                 ▼         ▼       ▼         ▼              ▼               ▼
         ┌───────────┐ ┌──────┐ ┌─────────────────┐ ┌──────────────┐ ┌────────────────────┐
         │ customers │ │users │ │loyalty_programs │ │business_     │ │promotional_        │
         └─────┬─────┘ └──────┘ └──┬──────┬───────┘ │locations     │ │events              │
               │                   │      │         └──────────────┘ └────────────────────┘
               │                   │      │
               │     ┌─────────────┘      │
               │     │                    │
               ▼     ▼                    ▼
         ┌──────────────┐          ┌─────────────┐
         │ enrollments  │          │card_designs │
         └──────┬───────┘          └──────┬──────┘
                │                         │
                │                         ▼
                │                  ┌──────────────────┐
                │                  │design_schedules  │
                │                  └──────────────────┘
                ▼
         ┌──────────────┐
         │ transactions │
         └──────────────┘

  loyalty_programs ──< notification_templates
  loyalty_programs ──< enrollments
  loyalty_programs ──< card_designs (via program_id FK)
  enrollments ──< transactions (via enrollment_id FK)
  businesses ──< stats_daily_rollup
  businesses ──< promotional_messages
  (scanner) ──> offline_queue
```

### Key Relationships

| Parent | Child | Cardinality | Notes |
|--------|-------|-------------|-------|
| businesses | loyalty_programs | 1:N | Multiple programs per business |
| loyalty_programs | card_designs | 1:N | Each design linked to a program |
| loyalty_programs | enrollments | 1:N | Customer progress per program |
| loyalty_programs | notification_templates | 1:N | Notification config per program |
| customers + programs | enrollments | N:M | Via enrollments junction |
| enrollments | transactions | 1:N | Each transaction tied to enrollment |
| businesses | business_locations | 1:N | Multiple locations per business |
| businesses | promotional_events | 1:N | Time-bounded behavior modifiers |
| businesses | promotional_messages | 1:N | Broadcast notifications |
| businesses | stats_daily_rollup | 1:N | Pre-aggregated daily stats |
| card_designs | design_schedules | 1:N | Scheduled design changes |

---

## 2. Complete SQL Schema

### 2.1 `loyalty_programs`

```sql
CREATE TABLE IF NOT EXISTS loyalty_programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('stamp', 'points', 'tiered')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_default BOOLEAN NOT NULL DEFAULT false,
    config JSONB NOT NULL DEFAULT '{}',
    reward_name TEXT,
    reward_description TEXT,
    back_fields JSONB DEFAULT '[]',
    translations JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Only one default program per business
CREATE UNIQUE INDEX IF NOT EXISTS idx_loyalty_programs_default
ON loyalty_programs(business_id) WHERE is_default = true;

CREATE INDEX IF NOT EXISTS idx_loyalty_programs_business
ON loyalty_programs(business_id);

CREATE INDEX IF NOT EXISTS idx_loyalty_programs_business_active
ON loyalty_programs(business_id) WHERE is_active = true;
```

**Config examples by type:**

```jsonc
// STAMP
{ "total_stamps": 10, "auto_reset_on_redeem": true }

// POINTS
{
  "points_per_visit": 10,
  "points_per_currency_unit": 1,
  "currency": "EUR",
  "rewards": [
    { "name": "Small Coffee", "points_required": 50 },
    { "name": "Large Coffee", "points_required": 100 }
  ]
}

// TIERED
{
  "tiers": [
    { "name": "Bronze", "threshold": 0, "benefits": ["5% discount"] },
    { "name": "Silver", "threshold": 100, "benefits": ["10% discount"] },
    { "name": "Gold", "threshold": 500, "benefits": ["20% discount"] }
  ],
  "points_per_visit": 10,
  "tier_evaluation_period": "rolling_year"
}
```

### 2.2 `enrollments`

```sql
CREATE TABLE IF NOT EXISTS enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    program_id UUID NOT NULL REFERENCES loyalty_programs(id) ON DELETE CASCADE,
    progress JSONB NOT NULL DEFAULT '{"stamps": 0}',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'paused', 'expired')),
    total_redemptions INT NOT NULL DEFAULT 0,
    last_activity_at TIMESTAMPTZ,
    enrolled_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(customer_id, program_id)
);

CREATE INDEX IF NOT EXISTS idx_enrollments_customer
ON enrollments(customer_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_program
ON enrollments(program_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_program_active
ON enrollments(program_id) WHERE status = 'active';
```

### 2.3 `notification_templates`

```sql
CREATE TABLE IF NOT EXISTS notification_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID NOT NULL REFERENCES loyalty_programs(id) ON DELETE CASCADE,
    trigger TEXT NOT NULL CHECK (trigger IN (
        'stamp_added', 'reward_earned', 'reward_redeemed',
        'milestone', 'inactivity', 'welcome',
        'tier_upgrade', 'tier_downgrade', 'points_expiring'
    )),
    trigger_config JSONB DEFAULT '{}',
    title_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    translations JSONB DEFAULT '{}',
    is_default BOOLEAN NOT NULL DEFAULT false,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    is_customized BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_templates_program
ON notification_templates(program_id);

CREATE INDEX IF NOT EXISTS idx_notification_templates_trigger
ON notification_templates(program_id, trigger) WHERE is_enabled = true;
```

### 2.4 `promotional_messages`

```sql
CREATE TABLE IF NOT EXISTS promotional_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    target_filter JSONB DEFAULT '{}',
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'scheduled', 'sending', 'sent', 'cancelled')),
    total_recipients INT DEFAULT 0,
    delivered INT DEFAULT 0,
    failed INT DEFAULT 0,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_promotional_messages_business
ON promotional_messages(business_id);

CREATE INDEX IF NOT EXISTS idx_promotional_messages_status
ON promotional_messages(status) WHERE status IN ('scheduled', 'sending');
```

### 2.5 `promotional_events`

```sql
CREATE TABLE IF NOT EXISTS promotional_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    program_id UUID REFERENCES loyalty_programs(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL CHECK (type IN ('multiplier', 'bonus', 'custom')),
    config JSONB NOT NULL DEFAULT '{}',
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    announcement_title TEXT,
    announcement_body TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CHECK (ends_at > starts_at)
);

CREATE INDEX IF NOT EXISTS idx_promotional_events_business
ON promotional_events(business_id);

CREATE INDEX IF NOT EXISTS idx_promotional_events_active
ON promotional_events(business_id, starts_at, ends_at) WHERE is_active = true;
```

### 2.6 `design_schedules`

```sql
CREATE TABLE IF NOT EXISTS design_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    design_id UUID NOT NULL REFERENCES card_designs(id) ON DELETE CASCADE,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ,
    is_revert BOOLEAN NOT NULL DEFAULT false,
    revert_to_design_id UUID REFERENCES card_designs(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'active', 'completed', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_design_schedules_business
ON design_schedules(business_id);

CREATE INDEX IF NOT EXISTS idx_design_schedules_pending
ON design_schedules(starts_at) WHERE status = 'scheduled';
```

### 2.7 `business_locations`

```sql
CREATE TABLE IF NOT EXISTS business_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    address TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    radius_meters INT DEFAULT 100,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_business_locations_business
ON business_locations(business_id);
```

### 2.8 `stats_daily_rollup`

```sql
CREATE TABLE IF NOT EXISTS stats_daily_rollup (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    program_id UUID REFERENCES loyalty_programs(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    stamps_added INT DEFAULT 0,
    rewards_redeemed INT DEFAULT 0,
    points_earned INT DEFAULT 0,
    points_redeemed INT DEFAULT 0,
    new_customers INT DEFAULT 0,
    active_customers INT DEFAULT 0,
    returning_customers INT DEFAULT 0,
    programs_completed INT DEFAULT 0,
    hourly_activity JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(business_id, program_id, date)
);

CREATE INDEX IF NOT EXISTS idx_stats_rollup_business_date
ON stats_daily_rollup(business_id, date);

CREATE INDEX IF NOT EXISTS idx_stats_rollup_program_date
ON stats_daily_rollup(program_id, date);
```

### 2.9 `offline_queue`

```sql
CREATE TABLE IF NOT EXISTS offline_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT NOT NULL UNIQUE,
    scanner_user_id UUID NOT NULL REFERENCES users(id),
    business_id UUID NOT NULL REFERENCES businesses(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    program_id UUID REFERENCES loyalty_programs(id),
    action TEXT NOT NULL CHECK (action IN ('stamp', 'redeem', 'void')),
    payload JSONB DEFAULT '{}',
    created_offline_at TIMESTAMPTZ NOT NULL,
    synced_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'synced', 'failed', 'conflict')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_offline_queue_business
ON offline_queue(business_id) WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_offline_queue_client_id
ON offline_queue(client_id);
```

### 2.10 Modified Tables

#### `card_designs` - Add `program_id`

```sql
ALTER TABLE card_designs
ADD COLUMN IF NOT EXISTS program_id UUID REFERENCES loyalty_programs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_card_designs_program
ON card_designs(program_id);

COMMENT ON COLUMN card_designs.total_stamps IS
    'DEPRECATED: Use loyalty_programs.config.total_stamps instead. Kept for backward compatibility during migration.';

COMMENT ON COLUMN card_designs.back_fields IS
    'DEPRECATED: Use loyalty_programs.back_fields instead. Kept for backward compatibility during migration.';
```

#### `transactions` - Add program/enrollment FKs + rename columns

```sql
ALTER TABLE transactions
ADD COLUMN IF NOT EXISTS program_id UUID REFERENCES loyalty_programs(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS enrollment_id UUID REFERENCES enrollments(id) ON DELETE SET NULL;

-- Rename columns (Phase 6 cleanup - not applied yet)
-- stamp_delta -> delta
-- stamps_before -> value_before
-- stamps_after -> value_after

-- Expand type CHECK to include new transaction types
ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_type_check;
ALTER TABLE transactions ADD CONSTRAINT transactions_type_check
CHECK (type IN (
    'stamp_added', 'reward_redeemed', 'stamp_voided', 'bonus_stamp', 'stamps_adjusted',
    'points_earned', 'points_redeemed', 'points_expired', 'points_adjusted',
    'tier_upgraded', 'tier_downgraded'
));

CREATE INDEX IF NOT EXISTS idx_transactions_program
ON transactions(program_id);

CREATE INDEX IF NOT EXISTS idx_transactions_enrollment
ON transactions(enrollment_id);
```

#### `push_registrations` - Add `enrollment_id`

```sql
ALTER TABLE push_registrations
ADD COLUMN IF NOT EXISTS enrollment_id UUID REFERENCES enrollments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_push_registrations_enrollment
ON push_registrations(enrollment_id);
```

---

## 3. RLS Policies

All new tables follow the same pattern: service_role has full access.

```sql
-- Apply to each new table:
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage {table_name}"
ON {table_name} FOR ALL
USING ((SELECT auth.role()) = 'service_role');
```

---

## 4. Data Migration SQL (Phase 2)

```sql
-- 4.1 Create default loyalty_program for each business with an active design
INSERT INTO loyalty_programs (business_id, name, type, is_active, is_default, config, reward_name, back_fields, translations)
SELECT
    cd.business_id,
    COALESCE(cd.name, 'Main Loyalty Program'),
    'stamp',
    true,
    true,
    jsonb_build_object(
        'total_stamps', COALESCE(cd.total_stamps, 10),
        'auto_reset_on_redeem', true
    ),
    NULL,
    COALESCE(cd.back_fields, '[]'::jsonb),
    COALESCE(cd.translations, '{}'::jsonb)
FROM card_designs cd
WHERE cd.is_active = true
ON CONFLICT DO NOTHING;

-- 4.2 Link card_designs to their programs
UPDATE card_designs cd
SET program_id = lp.id
FROM loyalty_programs lp
WHERE lp.business_id = cd.business_id
AND lp.is_default = true;

-- 4.3 Create enrollments from existing customers
INSERT INTO enrollments (customer_id, program_id, progress, status, total_redemptions, enrolled_at)
SELECT
    c.id,
    lp.id,
    jsonb_build_object('stamps', COALESCE(c.stamps, 0)),
    'active',
    COALESCE(c.total_redemptions, 0),
    c.created_at
FROM customers c
JOIN loyalty_programs lp ON lp.business_id = c.business_id AND lp.is_default = true
ON CONFLICT (customer_id, program_id) DO NOTHING;

-- 4.4 Backfill transactions with program_id and enrollment_id
UPDATE transactions t
SET
    program_id = lp.id,
    enrollment_id = e.id
FROM loyalty_programs lp
JOIN enrollments e ON e.program_id = lp.id
WHERE lp.business_id = t.business_id
AND lp.is_default = true
AND e.customer_id = t.customer_id
AND t.program_id IS NULL;

-- 4.5 Link push_registrations to enrollments
UPDATE push_registrations pr
SET enrollment_id = e.id
FROM enrollments e
JOIN loyalty_programs lp ON lp.id = e.program_id
WHERE e.customer_id = pr.customer_id
AND lp.business_id = (SELECT business_id FROM customers WHERE id = pr.customer_id)
AND lp.is_default = true
AND pr.enrollment_id IS NULL;
```

---

## 5. Service Layer Design

### 5.1 Program Engines (Strategy Pattern)

```
ProgramService
  ├── resolve_engine(program.type) -> BaseEngine
  ├── add_progress(customer_id, business_id, program_id?, amount=1)
  ├── redeem_reward(enrollment_id)
  └── get_or_create_enrollment(customer_id, program_id)

BaseEngine (abstract)
  ├── add_progress(enrollment, amount, modifiers) -> ProgressResult
  ├── redeem(enrollment) -> RedeemResult
  ├── check_milestones(enrollment) -> list[Milestone]
  └── get_display_value(enrollment) -> str

StampEngine(BaseEngine)
  - add_progress: increment stamps, cap at total_stamps
  - redeem: reset stamps to 0, increment total_redemptions
  - milestones: at 50%, 80%, 100%

PointsEngine(BaseEngine)
  - add_progress: add points based on config
  - redeem: deduct points for a specific reward
  - milestones: when reaching reward thresholds

TieredEngine(BaseEngine)
  - add_progress: add points, evaluate tier changes
  - redeem: deduct points (tier maintained)
  - milestones: tier upgrades/downgrades
```

### 5.2 Service Method Signatures

```python
# ProgramService
class ProgramService:
    async def add_progress(
        self,
        customer_id: str,
        business_id: str,
        program_id: str | None = None,  # None = use default program
        amount: int = 1,
        employee_id: str | None = None,
        source: str = "scanner",
    ) -> ProgressResult

    async def redeem_reward(
        self,
        enrollment_id: str,
        reward_index: int = 0,  # For points programs with multiple rewards
        employee_id: str | None = None,
    ) -> RedeemResult

    def get_or_create_enrollment(
        self,
        customer_id: str,
        program_id: str,
    ) -> dict  # enrollment record

    def get_default_program(self, business_id: str) -> dict | None

# NotificationService
class NotificationService:
    async def fire_trigger(
        self,
        program_id: str,
        trigger: str,
        context: dict,  # {customer_name, stamps, remaining, reward_name, ...}
    ) -> None

    async def send_promotional(self, message_id: str) -> dict

# EventService
class EventService:
    def get_active_events(
        self,
        business_id: str,
        program_id: str | None = None,
    ) -> list[dict]

    def calculate_modifiers(
        self,
        events: list[dict],
    ) -> EventModifiers  # {multiplier: float, bonus: int}
```

### 5.3 Data Types

```python
@dataclass
class ProgressResult:
    enrollment: dict
    delta: int  # actual amount added (after modifiers)
    value_before: int
    value_after: int
    milestones: list[str]  # triggered milestone names
    reward_earned: bool
    transaction_id: str

@dataclass
class RedeemResult:
    enrollment: dict
    value_before: int
    value_after: int
    reward_name: str
    transaction_id: str

@dataclass
class EventModifiers:
    multiplier: float = 1.0
    bonus: int = 0
```

---

## 6. Updated Stamp Flow

```
Scanner -> POST /stamps/{business_id}/{customer_id}
  |
  v
ProgramService.add_progress(customer_id, business_id, program_id=None)
  |
  ├── 1. Resolve program (default if none specified)
  │       ProgramRepository.get_default(business_id)
  │
  ├── 2. Get or create enrollment
  │       EnrollmentRepository.get_or_create(customer_id, program_id)
  │
  ├── 3. Check active promotional events
  │       EventService.get_active_events(business_id, program_id)
  │       -> EventModifiers { multiplier: 2, bonus: 0 }
  │
  ├── 4. Resolve engine by program type
  │       engine = StampEngine (based on program.type)
  │
  ├── 5. Apply progress
  │       result = engine.add_progress(enrollment, amount=1, modifiers)
  │       -> EnrollmentRepository.update_progress (atomic)
  │
  ├── 6. Check milestones -> fire NotificationService triggers
  │       NotificationService.fire_trigger(program_id, "stamp_added", context)
  │       if result.reward_earned:
  │           NotificationService.fire_trigger(program_id, "reward_earned", context)
  │
  ├── 7. Log transaction
  │       TransactionRepository.create(
  │           program_id, enrollment_id, delta=2 if doubled, ...
  │       )
  │
  └── 8. Update wallets
          design = CardDesignRepository.get_active_for_program(program_id)
          PassCoordinator.on_progress_updated(enrollment, program, design)
```

---

## 7. Back Fields: Three-Layer Inheritance

```
Layer 1: Business Defaults    (businesses.settings.default_back_fields)
                                    |
                              merge (program overrides by key)
                                    |
Layer 2: Program Fields       (loyalty_programs.back_fields)
                                    |
                              = final back_fields on pass
```

- **Business-level**: Static info (website, address, contact)
- **Program-level**: Program-specific (terms, reward description, expiry)
- **Design-level**: REMOVED for back_fields (designs keep only secondary_fields and auxiliary_fields)

Merge logic: program fields override business fields by `key`.

```python
def merge_back_fields(business: dict, program: dict) -> list[dict]:
    """Merge business default back_fields with program-specific ones."""
    business_fields = business.get("settings", {}).get("default_back_fields", [])
    program_fields = program.get("back_fields", [])

    # Build lookup by key
    merged = {f["key"]: f for f in business_fields}
    for field in program_fields:
        merged[field["key"]] = field  # Program overrides business

    return list(merged.values())
```

---

## 8. Multiple Programs: One Wallet Card Per Enrollment

Apple Wallet uniquely identifies passes by `passTypeIdentifier` + `serialNumber`. Each enrollment gets its own pass with a unique serial number.

**Key changes:**
- `serialNumber` = `enrollment_id` (currently `customer_id`)
- `pass.json.barcode` still encodes `customer_id` (scanner resolves enrollment from program context)
- `push_registrations.enrollment_id` links device to the correct pass
- Each enrollment's design comes via `card_designs.program_id`

**Example**: A customer at Marie's Bakery could have:
- "Main Stamps" card (enrollment 1): 7/10 stamps
- "Weekend Brunch" card (enrollment 2): 3/5 stamps

---

## 9. Promotional Events

Business creates event (e.g., "Double Stamp Weekend"):

```json
{
  "type": "multiplier",
  "config": { "multiplier": 2 },
  "starts_at": "2025-02-21T00:00:00Z",
  "ends_at": "2025-02-23T23:59:59Z"
}
```

During the event window, `ProgramService.add_progress()`:
1. Queries active events for the business/program
2. Calculates modifiers: 1 stamp * 2 = 2 stamps
3. Transaction metadata: `{"event_id": "...", "multiplier": 2}`

---

## 10. Design Schedules

Business schedules a design change (e.g., Christmas theme):

```json
{
  "design_id": "christmas-design-uuid",
  "starts_at": "2025-12-20T00:00:00Z",
  "ends_at": "2026-01-02T00:00:00Z",
  "is_revert": true,
  "revert_to_design_id": "original-design-uuid"
}
```

SchedulerService cron (every 5 minutes):
1. Activate designs where `starts_at <= now` and `status = 'scheduled'`
2. Revert designs where `ends_at <= now` and `is_revert = true`
3. Trigger strip regeneration and wallet updates on each change

---

## 11. Statistics Infrastructure

**Hybrid approach**: Real-time for today, historical from rollups.

| Metric | Source | Method |
|--------|--------|--------|
| Today's stamps/rewards | `transactions` | Direct query |
| Historical trends | `stats_daily_rollup` | Pre-aggregated |
| Peak hours | `hourly_activity` JSONB | From rollups |
| Completion rate | `programs_completed / active_customers` | Rollup fields |
| Customer segments | `customers.created_at` + `enrollments.last_activity_at` | Computed |

**Nightly rollup query** (runs as cron):

```sql
INSERT INTO stats_daily_rollup (business_id, program_id, date, stamps_added, rewards_redeemed, ...)
SELECT
    t.business_id,
    t.program_id,
    t.created_at::date AS date,
    COUNT(*) FILTER (WHERE t.type = 'stamp_added'),
    COUNT(*) FILTER (WHERE t.type = 'reward_redeemed'),
    ...
FROM transactions t
WHERE t.created_at::date = CURRENT_DATE - INTERVAL '1 day'
GROUP BY t.business_id, t.program_id, t.created_at::date
ON CONFLICT (business_id, program_id, date) DO UPDATE SET ...;
```

---

## 12. New API Routes

| Route | Method | Endpoint | Description |
|-------|--------|----------|-------------|
| Programs | GET | `/programs/{business_id}` | List programs for business |
| Programs | POST | `/programs/{business_id}` | Create new program |
| Programs | PATCH | `/programs/{business_id}/{program_id}` | Update program |
| Programs | POST | `/programs/{business_id}/{program_id}/activate` | Activate program |
| Programs | POST | `/programs/{business_id}/{program_id}/deactivate` | Deactivate program |
| Enrollments | GET | `/enrollments/{business_id}/{customer_id}` | Get customer enrollments |
| Enrollments | POST | `/enrollments/{business_id}` | Manually enroll customer |
| Notifications | GET | `/notifications/{business_id}/templates` | Get notification templates |
| Notifications | PATCH | `/notifications/{business_id}/templates/{id}` | Edit template |
| Notifications | POST | `/notifications/{business_id}/messages` | Create promotional message |
| Events | GET | `/events/{business_id}` | List events |
| Events | POST | `/events/{business_id}` | Create event |
| Events | PATCH | `/events/{business_id}/{event_id}` | Update event |
| Locations | GET | `/locations/{business_id}` | List locations |
| Locations | POST | `/locations/{business_id}` | Add location |
| Sync | POST | `/sync/{business_id}` | Process offline queue batch |
| Stats | GET | `/stats/{business_id}` | Dashboard stats |
| Stats | GET | `/stats/{business_id}/peak-hours` | Peak hours analysis |

**Backward compatibility**: Existing `/stamps/{business_id}/{customer_id}` preserved. It delegates to `ProgramService` using the default program.

---

## 13. Migration Strategy (Phased)

| Phase | What | Risk | Migration Files |
|-------|------|------|-----------------|
| 1 | Create new tables (programs, enrollments, notifications, events, schedules, locations, stats, offline) | Zero | 29-36 |
| 2-3 | Add FK columns + data migration (populate programs, enrollments, backfill transactions) | Low (INSERT + ALTER only) | 37-38 |
| 4 | Dual-write code (backend writes old columns AND new tables) | Code deployment | stamps.py updated |
| 5 | Switch reads to new tables | Code deployment | N/A |
| 6 | Cleanup: rename transaction columns, drop deprecated customer columns | After confidence period | Future migrations |

---

## 14. Feature Flags

```python
# New feature flags in features.py
PLAN_LIMITS = {
    SubscriptionTier.PAY: {
        "features": [
            "basic_analytics",
            "standard_notifications",
            # NEW:
            "single_program",       # Can only have 1 active program
        ]
    },
    SubscriptionTier.PRO: {
        "features": [
            "basic_analytics",
            "advanced_analytics",
            "standard_notifications",
            "custom_notifications",
            "scheduled_campaigns",
            "multiple_locations",
            "geofencing",
            "promotional_messaging",
            # NEW:
            "multiple_programs",     # Multiple concurrent programs
            "promotional_events",    # Double stamp weekends, etc.
            "design_schedules",      # Scheduled design changes
            "offline_sync",          # Scanner offline support
        ]
    }
}
```

---

## 15. Modified Services Summary

| Service | Change |
|---------|--------|
| `pass_generator.py` | Accepts `program` + `design` separately; reads `total_stamps` from `program.config`; merges back_fields from business + program |
| `wallets/coordinator.py` | `on_stamp_added` -> `on_progress_updated`; accepts program + enrollment + design |
| `wallets/google.py` | Object payload uses program config for stamps/points display |
| `wallets/strips.py` | Gets `total_stamps` from program config, not design |
| `strip_cache.py` | Cache key: `{design_id}:{program_id}:{stamp_count}` |

---

## 16. Offline Scanning

Scanner app stores local queue (AsyncStorage/SQLite). On reconnect:

```
POST /sync/{business_id}
Body: { "items": [
  {
    "client_id": "uuid-generated-on-device",
    "customer_id": "...",
    "program_id": "...",  // optional, uses default
    "action": "stamp",
    "payload": {},
    "created_offline_at": "2025-02-19T10:00:00Z"
  }
]}

Response: {
  "results": [
    { "client_id": "...", "status": "synced", "transaction_id": "..." },
    { "client_id": "...", "status": "conflict", "reason": "Already at max stamps" }
  ]
}
```

- `client_id` provides idempotency (UNIQUE constraint)
- Items >24h old are rejected
- Optimistic UI with "pending sync" indicator when offline
