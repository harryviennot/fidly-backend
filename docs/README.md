# Backend Documentation

## Wallet Integration

The platform supports both Apple Wallet and Google Wallet for loyalty card passes.

### Documentation

| Document | Description |
|----------|-------------|
| [Wallet Integration API](wallet-integration-api.md) | Complete API reference with all routes, arguments, responses, and usage examples |
| [Google Wallet Integration](google-wallet-integration.md) | Deep dive into Google Wallet implementation, architecture, and troubleshooting |

### Quick Links

**API Routes:**
- Customer endpoints: `POST/GET /customers/{business_id}`
- Stamp endpoints: `POST /stamps/{business_id}/{customer_id}`
- Design endpoints: `POST/PUT/DELETE /designs/{business_id}`
- Pass download: `GET /passes/{customer_id}`
- Apple Wallet callbacks: `/wallet/v1/*`
- Google Wallet callback: `POST /google-wallet/callback`

**Services:**
- `PassCoordinator` - Orchestrates wallet operations
- `GoogleWalletService` - Google Wallet API integration
- `AppleWalletService` - Apple Wallet pass generation
- `StripImageService` - Pre-generates stamp images

**Key Concepts:**
- One Google Wallet class per business
- Pre-generated strip images for fast loading
- Unified wallet registration tracking
- Background processing for design updates

### Getting Started

1. Configure environment variables:
   ```bash
   GOOGLE_WALLET_ISSUER_ID=your-issuer-id
   GOOGLE_WALLET_CREDENTIALS_PATH=certs/google-wallet-key.json
   ```

2. Apply database migrations:
   ```bash
   # Migration 12: Base Google Wallet support
   # Migration 13: Strip images and callback nonces
   ```

3. Use the PassCoordinator in your code:
   ```python
   from app.services.wallets import create_pass_coordinator

   coordinator = create_pass_coordinator()
   urls = coordinator.get_wallet_urls(customer, business, design)
   ```
