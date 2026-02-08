# Wallet Services

This package provides unified wallet integration for Apple Wallet and Google Wallet.

## Quick Start

```python
from app.services.wallets import create_pass_coordinator

# Create coordinator (lazy-loads services)
coordinator = create_pass_coordinator()

# Get wallet URLs for a customer
urls = coordinator.get_wallet_urls(customer, business, design)
# {"apple_url": "https://.../passes/123", "google_url": "https://pay.google.com/..."}

# Handle stamp updates (updates both wallets)
await coordinator.on_stamp_added(customer, business, design)

# Pre-generate strips for a new design
coordinator.pregenerate_strips_for_design(design, business_id)
```

## Architecture

```
PassCoordinator (Orchestrator)
       │
       ├── AppleWalletService
       │       ├── PassGenerator (creates .pkpass files)
       │       └── APNsClient (push notifications)
       │
       ├── GoogleWalletService
       │       ├── GenericClass management
       │       ├── GenericObject management
       │       └── JWT-signed save URLs
       │
       └── StripImageService
               ├── StripImageGenerator (creates images)
               └── StorageService (uploads to Supabase)
```

## Services

### PassCoordinator
The main entry point. Orchestrates operations across both platforms.

| Method | Description |
|--------|-------------|
| `get_wallet_urls()` | Returns Apple and Google wallet URLs |
| `on_customer_created()` | Called after customer creation |
| `on_stamp_added()` | Updates both wallets after stamp change |
| `on_design_updated()` | Regenerates strips, notifies customers |
| `on_design_activated()` | Updates Google class |
| `pregenerate_strips_for_design()` | Creates all strip images |

### GoogleWalletService
Handles Google Wallet API interactions.

| Method | Description |
|--------|-------------|
| `create_or_update_class()` | Manages GenericClass |
| `create_object()` | Creates GenericObject for customer |
| `update_object()` | Updates existing object |
| `generate_save_url()` | Creates JWT-signed save URL |
| `handle_callback()` | Processes save/delete callbacks |

### AppleWalletService
Wraps existing Apple Wallet functionality.

| Method | Description |
|--------|-------------|
| `generate_pass()` | Creates .pkpass file |
| `get_pass_url()` | Returns pass download URL |
| `send_update()` | Sends APNs push notification |

### StripImageService
Pre-generates strip images for both platforms.

| Method | Description |
|--------|-------------|
| `pregenerate_all_strips()` | Generates all strips for a design |
| `get_strip_url()` | Gets URL from database |
| `delete_strips_for_design()` | Removes all strips |

## Configuration

Required environment variables:
```bash
GOOGLE_WALLET_ISSUER_ID=3388000000023082278
GOOGLE_WALLET_CREDENTIALS_PATH=certs/google-wallet-key.json
```

## Database Tables

- `strip_images` - Pre-generated strip URLs
- `google_callback_nonces` - Callback deduplication
- `push_registrations` - Wallet registrations (both platforms)
- `businesses.google_class_id` - Google class per business

## Full Documentation

See [docs/google-wallet-integration.md](../../../docs/google-wallet-integration.md) for comprehensive documentation including:
- Detailed architecture diagrams
- API endpoint documentation
- Flow diagrams
- Error handling
- Testing guide
