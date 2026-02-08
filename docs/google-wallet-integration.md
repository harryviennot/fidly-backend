# Google Wallet Integration Documentation

This document provides comprehensive documentation for the Google Wallet integration in the Fidelity/Stampeo loyalty card platform.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Database Schema](#database-schema)
4. [Service Layer](#service-layer)
5. [API Endpoints](#api-endpoints)
6. [Configuration](#configuration)
7. [Key Flows](#key-flows)
8. [Strip Image Pre-generation](#strip-image-pre-generation)
9. [Error Handling](#error-handling)
10. [Testing](#testing)

---

## Overview

### Why Google Wallet Integration?

The platform previously only supported Apple Wallet passes. This integration adds Google Wallet support, allowing Android users to save loyalty cards to their Google Wallet app.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Pass Type** | Generic Pass (not Loyalty Pass) | Loyalty Pass doesn't allow per-customer hero images. Generic Pass allows unique stamp visuals per customer. |
| **Class Scope** | One class per BUSINESS | Simpler model. When active design changes, update the existing class rather than creating new ones. |
| **Strip Generation** | Pre-generate all images | Google fetches images via URL. Pre-generating avoids slow on-demand generation blocking Google's image fetch. |
| **Generation Timing** | Sync on create, async on update | Design creation blocks until strips are ready. Updates to active designs use background jobs. |
| **Wallet Buttons** | Always show both | Let users choose Apple or Google Wallet regardless of device detection. |

### Google Wallet Concepts

- **GenericClass**: A template shared by all customers of a business. Contains branding, colors, and callback URLs.
- **GenericObject**: An individual pass instance for each customer. Contains customer-specific data like name, stamp count, and hero image URL.
- **Save URL**: A JWT-signed URL that, when clicked, adds the pass to Google Wallet.
- **Callbacks**: Google sends HTTP POST requests when users save or delete passes.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         API Layer                                    │
├─────────────────────────────────────────────────────────────────────┤
│  customers.py  │  stamps.py  │  designs.py  │  google_wallet.py     │
└───────┬────────┴──────┬──────┴──────┬───────┴──────────┬────────────┘
        │               │             │                   │
        └───────────────┴─────────────┴───────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │    PassCoordinator    │
                    │   (Orchestrator)      │
                    └───────────┬───────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
┌───────▼───────┐     ┌─────────▼─────────┐   ┌────────▼────────┐
│AppleWallet    │     │ GoogleWallet      │   │ StripImage      │
│Service        │     │ Service           │   │ Service         │
└───────┬───────┘     └─────────┬─────────┘   └────────┬────────┘
        │                       │                      │
        │                       │                      │
┌───────▼───────┐     ┌─────────▼─────────┐   ┌────────▼────────┐
│ APNsClient    │     │ Google Wallet API │   │ StripGenerator  │
│ PassGenerator │     │ (REST + JWT)      │   │ StorageService  │
└───────────────┘     └───────────────────┘   └─────────────────┘
```

### File Structure

```
backend/app/
├── services/
│   └── wallets/
│       ├── __init__.py           # Package exports
│       ├── apple.py              # AppleWalletService
│       ├── google.py             # GoogleWalletService
│       ├── coordinator.py        # PassCoordinator
│       └── strips.py             # StripImageService
├── repositories/
│   ├── wallet_registration.py    # Unified wallet registrations
│   ├── strip_image.py            # Pre-generated strip URLs
│   ├── callback_nonce.py         # Google callback deduplication
│   └── device.py                 # Apple device registrations (filtered)
└── api/routes/
    ├── google_wallet.py          # Callback endpoint
    ├── customers.py              # Returns both wallet URLs
    ├── stamps.py                 # Updates both wallets
    └── designs.py                # Strip pre-generation
```

---

## Database Schema

### Tables Added/Modified

#### `businesses` (modified)
```sql
ALTER TABLE businesses
ADD COLUMN IF NOT EXISTS google_class_id TEXT;
```
Stores the Google Wallet class ID for each business. Format: `{issuerId}.{businessId}`.

#### `strip_images` (new)
```sql
CREATE TABLE IF NOT EXISTS strip_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    design_id UUID NOT NULL REFERENCES card_designs(id) ON DELETE CASCADE,
    stamp_count INT NOT NULL CHECK (stamp_count >= 0),
    platform TEXT NOT NULL CHECK (platform IN ('apple', 'google')),
    resolution TEXT NOT NULL,  -- '1x', '2x', '3x' for Apple; 'hero' for Google
    url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(design_id, stamp_count, platform, resolution)
);
```
Stores URLs of pre-generated strip images for both platforms.

#### `google_callback_nonces` (new)
```sql
CREATE TABLE IF NOT EXISTS google_callback_nonces (
    nonce TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);
```
Prevents duplicate processing of Google Wallet callbacks.

#### `push_registrations` (modified in migration 12)
```sql
-- Already exists with these columns:
wallet_type TEXT NOT NULL DEFAULT 'apple'  -- 'apple' or 'google'
google_object_id TEXT                       -- For Google registrations
```

### Entity Relationships

```
businesses
    └── card_designs (1:N)
            └── strip_images (1:N, one per stamp count per platform)
    └── customers (1:N)
            └── push_registrations (1:N, both Apple and Google)
```

---

## Service Layer

### PassCoordinator

The `PassCoordinator` orchestrates operations across both Apple and Google Wallet services. It's the primary interface used by API routes.

**Location**: `backend/app/services/wallets/coordinator.py`

**Key Methods**:

| Method | Description |
|--------|-------------|
| `get_wallet_urls(customer, business, design)` | Returns both Apple and Google save URLs |
| `on_customer_created(customer, business, design)` | Called after customer creation, returns wallet URLs |
| `on_stamp_added(customer, business, design)` | Updates both wallets after stamp change |
| `on_design_updated(business, design)` | Regenerates strips and notifies all customers |
| `on_design_activated(business, design)` | Updates Google class, verifies strips exist |
| `pregenerate_strips_for_design(design, business_id)` | Generates all strip images for a design |

**Usage Example**:
```python
from app.services.wallets import create_pass_coordinator

coordinator = create_pass_coordinator()

# Get wallet URLs for a customer
urls = coordinator.get_wallet_urls(customer, business, design)
# Returns: {"apple_url": "...", "google_url": "..."}

# After adding a stamp
await coordinator.on_stamp_added(customer, business, design)
```

### GoogleWalletService

Handles all Google Wallet API interactions.

**Location**: `backend/app/services/wallets/google.py`

**Key Methods**:

| Method | Description |
|--------|-------------|
| `create_or_update_class(business, design)` | Creates or updates the GenericClass |
| `create_object(customer, business, design, stamp_count)` | Creates a GenericObject for a customer |
| `update_object(customer, business, design, stamp_count)` | Updates an existing object |
| `generate_save_url(customer, business, design, stamp_count)` | Generates JWT-signed save URL |
| `handle_callback(callback_data)` | Processes save/delete callbacks |

**Authentication**:
- Uses Google Service Account credentials
- JWT tokens signed with RS256 algorithm
- Scopes: `https://www.googleapis.com/auth/wallet_object.issuer`

**Class Payload Structure**:
```python
{
    "id": "{issuerId}.{businessId}",
    "classTemplateInfo": {...},
    "hexBackgroundColor": "#8B5A2B",
    "heroImage": {"sourceUri": {"uri": "..."}},
    "callbackOptions": {
        "url": "https://your-domain.com/google-wallet/callback"
    }
}
```

**Object Payload Structure**:
```python
{
    "id": "{issuerId}.{customerId}",
    "classId": "{issuerId}.{businessId}",
    "state": "ACTIVE",
    "heroImage": {
        "sourceUri": {"uri": "https://...strip_5.png"}
    },
    "textModulesData": [
        {"id": "stamps", "header": "STAMPS", "body": "5 / 10"},
        {"id": "reward", "header": "REWARD", "body": "Free Coffee"}
    ],
    "cardTitle": {"defaultValue": {"value": "Coffee Shop"}},
    "header": {"defaultValue": {"value": "John Doe"}},
    "barcode": {"type": "QR_CODE", "value": "{customerId}"}
}
```

### AppleWalletService

Wraps existing Apple Wallet functionality (PassGenerator, APNsClient) with a unified interface.

**Location**: `backend/app/services/wallets/apple.py`

**Key Methods**:

| Method | Description |
|--------|-------------|
| `generate_pass(customer, design)` | Generates .pkpass file |
| `get_pass_url(customer)` | Returns pass download URL |
| `send_update(customer_id)` | Sends APNs push to update pass |
| `send_update_to_all_customers(business_id)` | Notifies all customers of a business |

### StripImageService

Pre-generates strip images for both platforms.

**Location**: `backend/app/services/wallets/strips.py`

**Key Methods**:

| Method | Description |
|--------|-------------|
| `pregenerate_all_strips(design, business_id)` | Generates all strips (0 to total_stamps) |
| `get_strip_url(design_id, stamp_count, platform, resolution)` | Gets URL from database |
| `get_apple_strip_urls(design_id, stamp_count)` | Gets all Apple resolutions |
| `get_google_hero_url(design_id, stamp_count)` | Gets Google hero image URL |
| `delete_strips_for_design(design_id)` | Deletes all strips for a design |

**Image Dimensions**:
- Apple: 375x144 (1x), 750x288 (2x), 1125x432 (3x)
- Google Hero: 1032x336

---

## API Endpoints

### Google Wallet Callback

**Endpoint**: `POST /google-wallet/callback`

**Purpose**: Receives callbacks from Google when users save or delete passes.

**Request Body** (from Google):
```json
{
    "eventType": "save",
    "classId": "3388000000023082278.business-uuid",
    "objectId": "3388000000023082278.customer-uuid",
    "nonce": "unique-nonce-id"
}
```

**Event Types**:
- `save`: User added pass to Google Wallet
- `del`: User removed pass from Google Wallet

**Response**:
```json
{
    "status": "ok",
    "result": {
        "action": "save",
        "customer_id": "customer-uuid",
        "registered": true
    }
}
```

**Verification Endpoint**: `GET /google-wallet/callback`
Returns `{"status": "ok"}` for Google to verify the callback URL is reachable.

### Customer Endpoints (Modified)

**Endpoint**: `POST /customers/{business_id}`

**Response** (now includes Google Wallet URL):
```json
{
    "id": "customer-uuid",
    "name": "John Doe",
    "email": "john@example.com",
    "stamps": 0,
    "pass_url": "https://api.example.com/passes/customer-uuid",
    "google_wallet_url": "https://pay.google.com/gp/v/save/eyJ..."
}
```

### Stamp Endpoints (Modified)

**Endpoint**: `POST /stamps/{business_id}/{customer_id}`

**Behavior**: Now updates both Apple Wallet (via APNs push) and Google Wallet (via API update).

---

## Configuration

### Environment Variables

```bash
# Google Wallet (required for Google Wallet support)
GOOGLE_WALLET_ISSUER_ID=3388000000023082278
GOOGLE_WALLET_CREDENTIALS_PATH=certs/google-wallet-key.json

# Tunnel URL (for callbacks - set by docker-compose)
TUNNEL_URL_FILE=/tunnel/url
```

### Google Cloud Setup

1. **Enable Google Wallet API** in Google Cloud Console
2. **Create Service Account** with "Google Wallet API" role
3. **Download JSON key** to `certs/google-wallet-key.json`
4. **Configure Issuer Account** at pay.google.com/business/console

### Callback URL Configuration

The callback URL is dynamically constructed from the cloudflared tunnel:

```python
# backend/app/core/config.py
def get_callback_url() -> str:
    tunnel_url = get_tunnel_url()  # Reads from /tunnel/url file
    base = tunnel_url if tunnel_url else settings.base_url
    return f"{base}/google-wallet/callback"
```

This ensures Google can reach your callback endpoint even during local development (via cloudflared tunnel).

---

## Key Flows

### 1. Customer Registration Flow

```
User registers on web portal
         │
         ▼
POST /customers/{business_id}
         │
         ├──► CustomerRepository.create()
         │
         ▼
PassCoordinator.on_customer_created()
         │
         ├──► AppleWalletService.get_pass_url()
         │         │
         │         └──► Returns "/passes/{customer_id}"
         │
         └──► GoogleWalletService.generate_save_url()
                   │
                   ├──► Build class payload
                   ├──► Build object payload
                   ├──► Sign JWT with service account key
                   └──► Return "https://pay.google.com/gp/v/save/{jwt}"
         │
         ▼
Return both URLs to client
```

### 2. Stamp Added Flow

```
Scanner app scans QR code
         │
         ▼
POST /stamps/{business_id}/{customer_id}
         │
         ├──► CustomerRepository.add_stamp()
         │
         ▼
PassCoordinator.on_stamp_added()
         │
         ├──► Check WalletRegistrationRepository
         │
         ├──► [If Apple registered]
         │         │
         │         └──► AppleWalletService.send_update()
         │                   │
         │                   └──► APNsClient.send_to_all_devices()
         │
         └──► [If Google registered]
                   │
                   └──► GoogleWalletService.update_object()
                             │
                             ├──► Get new hero image URL from strip_images
                             ├──► Build updated object payload
                             └──► PATCH to Google Wallet API
```

### 3. Design Creation Flow

```
Business owner creates design
         │
         ▼
POST /designs/{business_id}
         │
         ├──► CardDesignRepository.create()
         │
         ▼
PassCoordinator.pregenerate_strips_for_design()  ◄── SYNCHRONOUS (blocking)
         │
         ├──► StripImageService.pregenerate_all_strips()
         │         │
         │         ├──► For stamp_count 0 to total_stamps:
         │         │         │
         │         │         ├──► Generate Apple strips (1x, 2x, 3x)
         │         │         ├──► Generate Google hero (1032x336)
         │         │         ├──► Upload to Supabase Storage
         │         │         └──► Store URLs in strip_images table
         │         │
         │         └──► Return all URLs
         │
         ▼
Return design (strips ready for activation)
```

### 4. Design Update Flow (Active Design)

```
Business owner updates active design
         │
         ▼
PUT /designs/{business_id}/{design_id}
         │
         ├──► CardDesignRepository.update()
         │
         ├──► [If affects strips?]
         │         │
         │         └──► Yes: Schedule background task
         │
         ▼
Return immediately (200 OK)
         │
         ▼
Background Task (async):
         │
         ├──► StripImageService.delete_strips_for_design()
         ├──► StripImageService.pregenerate_all_strips()
         │
         ├──► GoogleWalletService.create_or_update_class()
         │
         ├──► For each customer:
         │         ├──► AppleWalletService.send_update()
         │         └──► GoogleWalletService.update_object()
         │
         ▼
All customers notified with new design
```

### 5. Google Wallet Save Callback Flow

```
User clicks "Add to Google Wallet" button
         │
         ▼
Google Wallet app processes JWT
         │
         ├──► Creates/updates object in Google's system
         │
         ▼
Google sends callback to our server
         │
         ▼
POST /google-wallet/callback
         │
         ├──► Check nonce in CallbackNonceRepository
         │         │
         │         ├──► [Already exists?] Return 200 (duplicate)
         │         │
         │         └──► [New?] Mark as processed
         │
         ├──► GoogleWalletService.handle_callback()
         │         │
         │         ├──► [eventType == "save"]
         │         │         │
         │         │         └──► WalletRegistrationRepository.register_google()
         │         │
         │         └──► [eventType == "del"]
         │                   │
         │                   └──► WalletRegistrationRepository.unregister_google()
         │
         ▼
Return 200 OK
```

---

## Strip Image Pre-generation

### Why Pre-generate?

Google Wallet fetches images from URLs you provide. If we generated images on-demand:
1. Google's image fetcher has a timeout (~5 seconds)
2. Dynamic generation can take 2-10 seconds
3. Failed image fetches show broken/empty hero images

By pre-generating all possible strip images when a design is created, we ensure fast response times (<50ms via Supabase CDN).

### Storage Structure

```
Supabase Storage: businesses bucket
└── {business_id}/
    └── cards/
        └── {design_id}/
            └── strips/
                ├── apple/
                │   ├── strip_0@1x.png
                │   ├── strip_0@2x.png
                │   ├── strip_0@3x.png
                │   ├── strip_1@1x.png
                │   ├── ...
                │   └── strip_10@3x.png
                └── google/
                    ├── hero_0.png
                    ├── hero_1.png
                    ├── ...
                    └── hero_10.png
```

### Generation Algorithm

```python
def pregenerate_all_strips(design, business_id):
    total_stamps = design["total_stamps"]  # e.g., 10

    for stamp_count in range(total_stamps + 1):  # 0 to 10
        # Apple: Generate at 3 resolutions
        for scale in [1, 2, 3]:
            image = generator.generate_at_scale(stamp_count, scale)
            url = storage.upload(f"strip_{stamp_count}@{scale}x.png")
            db.insert(design_id, stamp_count, "apple", f"{scale}x", url)

        # Google: Generate hero at 1032x336
        hero = generator.generate_google_hero(stamp_count)
        url = storage.upload(f"hero_{stamp_count}.png")
        db.insert(design_id, stamp_count, "google", "hero", url)
```

### Timing Considerations

| Scenario | Behavior | Rationale |
|----------|----------|-----------|
| Design created | Synchronous generation | Blocks until complete. Design can't be activated without strips. |
| Inactive design updated | Synchronous generation | Not in use, safe to block. |
| Active design updated | Background generation | Don't block the API response. Notify customers after complete. |
| Design activated | Check strips exist | Should already exist from creation. Fallback: generate synchronously. |

---

## Error Handling

### Graceful Degradation

All wallet operations are wrapped in try/catch blocks to prevent failures from breaking core functionality:

```python
# Example from stamps.py
try:
    await coordinator.on_stamp_added(customer, business, design)
except Exception as e:
    print(f"Wallet update error: {e}")
    # Stamp is still added - wallet update failure is non-fatal
```

### Common Error Scenarios

| Error | Cause | Handling |
|-------|-------|----------|
| Google API 401 | Invalid/expired credentials | Log error, return Apple URL only |
| Google API 404 | Object doesn't exist | Create new object instead of update |
| Strip generation timeout | Complex design, slow network | Log error, continue without strips |
| Callback nonce exists | Duplicate callback from Google | Return 200 OK (idempotent) |
| Storage upload failure | Supabase issues | Retry with exponential backoff |

### Logging

All services log errors with context:
```python
print(f"Google Wallet update error: {e}")
print(f"Strip pre-generation error: {e}")
print(f"Wallet URL generation error: {e}")
```

---

## Testing

### Unit Test Examples

```python
# Test strip generation
def test_generate_google_hero():
    generator = StripImageGenerator(config=StripConfig(total_stamps=10))
    hero_bytes = generator.generate_google_hero(stamps=5)

    # Verify dimensions
    img = Image.open(io.BytesIO(hero_bytes))
    assert img.size == (1032, 336)

# Test wallet URL generation
def test_generate_save_url():
    service = GoogleWalletService(
        credentials_path="certs/test-key.json",
        issuer_id="123456789"
    )

    url = service.generate_save_url(
        customer={"id": "cust-123", "name": "Test"},
        business={"id": "biz-123", "name": "Test Shop"},
        design={"id": "design-123", "total_stamps": 10},
        stamp_count=5
    )

    assert url.startswith("https://pay.google.com/gp/v/save/")
```

### Integration Test Flow

1. **Create design** → Verify strips generated in storage
2. **Create customer** → Verify both wallet URLs returned
3. **Add stamp** → Verify Google object updated (mock API)
4. **Simulate callback** → Verify registration created

### Manual E2E Testing

1. Create a business and design in the web portal
2. Create a customer → Note both wallet URLs
3. Click Apple Wallet URL → Verify pass downloads
4. Click Google Wallet URL → Verify pass saves to Google Wallet
5. Add stamp via scanner app → Verify both passes update
6. Update design colors → Verify all passes reflect changes

### Test Configuration

For local testing without real Google credentials:
```python
# Mock the Google Wallet service
class MockGoogleWalletService:
    def generate_save_url(self, *args, **kwargs):
        return "https://pay.google.com/gp/v/save/mock-jwt"

    def update_object(self, *args, **kwargs):
        return "mock-object-id"
```

---

## Troubleshooting

### Common Issues

**Q: Google Wallet URL is None**
- Check `GOOGLE_WALLET_ISSUER_ID` is set
- Verify service account JSON exists at configured path
- Ensure service account has Google Wallet API permissions

**Q: Callbacks not received**
- Verify cloudflared tunnel is running
- Check callback URL is publicly accessible
- Ensure `/google-wallet/callback` route is registered

**Q: Strip images show broken**
- Check Supabase Storage bucket is public
- Verify strip_images table has URLs for that design
- Regenerate strips: call `coordinator.pregenerate_strips_for_design()`

**Q: Pass doesn't update after stamp**
- Check if customer has Google registration in `push_registrations`
- Verify `wallet_type = 'google'` in registration
- Check Google API response for errors

---

## Future Improvements

1. **Rate Limiting**: Google has a 3 notifications per 24 hours limit per object. Implement tracking in `google_wallet_notifications` table.

2. **Push Updates**: Google Wallet doesn't support push like Apple. Consider implementing periodic refresh or webhook-based updates.

3. **Analytics**: Track save/delete events for business insights.

4. **Multi-language**: Support localized pass content via Google's `translatedValues`.

5. **Batch Operations**: Use Google's batch API for updating multiple objects efficiently.
