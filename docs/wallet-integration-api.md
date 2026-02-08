# Wallet Integration API Documentation

Complete API reference and architecture documentation for Apple Wallet and Google Wallet integration.

## Table of Contents

1. [API Routes Reference](#api-routes-reference)
   - [Customer Endpoints](#customer-endpoints)
   - [Stamp Endpoints](#stamp-endpoints)
   - [Design Endpoints](#design-endpoints)
   - [Pass Endpoints](#pass-endpoints)
   - [Apple Wallet Endpoints](#apple-wallet-endpoints)
   - [Google Wallet Endpoints](#google-wallet-endpoints)
2. [Response Schemas](#response-schemas)
3. [Authentication](#authentication)
4. [Architecture](#architecture)
5. [Service Layer API](#service-layer-api)
6. [Repository Layer API](#repository-layer-api)
7. [Usage Examples](#usage-examples)
8. [Error Handling](#error-handling)

---

## API Routes Reference

### Customer Endpoints

#### Create Customer

Creates a new customer and returns wallet URLs for both platforms.

```
POST /customers/{business_id}
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_id` | UUID | Yes | The business ID |

**Request Body:**
```json
{
    "name": "John Doe",
    "email": "john@example.com"
}
```

**Response:** `CustomerResponse` (201 Created)
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "John Doe",
    "email": "john@example.com",
    "stamps": 0,
    "pass_url": "https://api.example.com/passes/550e8400-e29b-41d4-a716-446655440000",
    "google_wallet_url": "https://pay.google.com/gp/v/save/eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
}
```

**Behavior:**
- If customer with same email exists for this business, returns existing customer with wallet URLs
- Generates auth token for Apple Wallet pass authentication
- Calls `PassCoordinator.on_customer_created()` to generate both wallet URLs
- Google Wallet URL is a JWT-signed save URL that can be clicked directly

**When to Use:**
- Customer registration form submission
- Adding customers via admin dashboard
- Importing customers from external systems

**Authentication:** Requires business membership (any role)

---

#### List Customers

Returns all customers for a business with their wallet URLs.

```
GET /customers/{business_id}
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_id` | UUID | Yes | The business ID |

**Response:** `List[CustomerResponse]` (200 OK)
```json
[
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "John Doe",
        "email": "john@example.com",
        "stamps": 5,
        "pass_url": "https://api.example.com/passes/550e8400-...",
        "google_wallet_url": "https://pay.google.com/gp/v/save/eyJ..."
    },
    {
        "id": "660e8400-e29b-41d4-a716-446655440001",
        "name": "Jane Smith",
        "email": "jane@example.com",
        "stamps": 10,
        "pass_url": "https://api.example.com/passes/660e8400-...",
        "google_wallet_url": "https://pay.google.com/gp/v/save/eyJ..."
    }
]
```

**Performance Note:** Generates wallet URLs for each customer. For large customer lists, consider pagination or lazy-loading wallet URLs.

**When to Use:**
- Admin dashboard customer list
- Bulk operations on customers
- Analytics and reporting

**Authentication:** Requires business membership (any role)

---

#### Get Customer

Returns a single customer with wallet URLs.

```
GET /customers/{business_id}/{customer_id}
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_id` | UUID | Yes | The business ID |
| `customer_id` | UUID | Yes | The customer ID |

**Response:** `CustomerResponse` (200 OK)

**Error Responses:**
| Status | Description |
|--------|-------------|
| 404 | Customer not found or doesn't belong to business |

**When to Use:**
- Customer detail page
- QR code scanning result display
- Before performing stamp operations

**Authentication:** Requires business membership (any role)

---

### Stamp Endpoints

#### Add Stamp

Adds a stamp to a customer and updates both wallet passes.

```
POST /stamps/{business_id}/{customer_id}
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_id` | UUID | Yes | The business ID |
| `customer_id` | UUID | Yes | The customer ID |

**Request Body:** None (empty)

**Response:** `StampResponse` (200 OK)
```json
{
    "customer_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "John Doe",
    "stamps": 6,
    "message": "Stamp added!"
}
```

**Special Messages:**
| Condition | Message |
|-----------|---------|
| Normal stamp | "Stamp added!" |
| Reached max stamps | "Congratulations! You've earned a reward!" |
| Already at max | "Already at maximum stamps! Ready for reward." |

**Wallet Update Behavior:**
1. Increments stamp count in database
2. Records scanner activity for analytics
3. Calls `PassCoordinator.on_stamp_added()`:
   - **Apple Wallet:** Sends APNs push notification → device fetches updated pass
   - **Google Wallet:** Calls Google API to update object with new hero image URL

**Error Responses:**
| Status | Description |
|--------|-------------|
| 404 | Customer not found or doesn't belong to business |

**When to Use:**
- Scanner app after QR code scan
- Manual stamp addition from admin dashboard
- Automated stamp rules (e.g., after purchase)

**Authentication:** Requires business membership (any role: owner or scanner)

---

#### Redeem Reward

Resets stamps to 0 after customer redeems their reward.

```
POST /stamps/{business_id}/{customer_id}/redeem
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_id` | UUID | Yes | The business ID |
| `customer_id` | UUID | Yes | The customer ID |

**Request Body:** None (empty)

**Response:** `StampResponse` (200 OK)
```json
{
    "customer_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "John Doe",
    "stamps": 0,
    "message": "Reward redeemed! Card has been reset."
}
```

**Behavior:**
- Validates customer has maximum stamps
- Resets stamps to 0
- Updates both wallet passes (same as add stamp)

**Error Responses:**
| Status | Description |
|--------|-------------|
| 400 | Customer doesn't have enough stamps for reward |
| 404 | Customer not found or doesn't belong to business |

**When to Use:**
- Scanner app redeem button
- Point of sale integration
- Admin dashboard reward management

**Authentication:** Requires business membership (any role)

---

### Design Endpoints

#### Create Design

Creates a new card design and pre-generates all strip images.

```
POST /designs/{business_id}
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_id` | UUID | Yes | The business ID |

**Request Body:** `CardDesignCreate`
```json
{
    "name": "Summer Promo",
    "organization_name": "Coffee Shop",
    "description": "Collect stamps for free coffee",
    "logo_text": "CS",
    "foreground_color": "rgb(255, 255, 255)",
    "background_color": "rgb(139, 90, 43)",
    "label_color": "rgb(200, 200, 200)",
    "total_stamps": 10,
    "stamp_filled_color": "rgb(255, 215, 0)",
    "stamp_empty_color": "rgb(80, 50, 20)",
    "stamp_border_color": "rgb(255, 255, 255)",
    "stamp_icon": "coffee",
    "reward_icon": "gift",
    "icon_color": "#ffffff",
    "secondary_fields": [],
    "auxiliary_fields": [],
    "back_fields": []
}
```

**Response:** `CardDesignResponse` (201 Created)

**Strip Pre-generation (Synchronous):**
This endpoint blocks until all strip images are generated:
- Apple: 3 resolutions × (total_stamps + 1) images = 33 images for 10 stamps
- Google: 1 hero × (total_stamps + 1) images = 11 images for 10 stamps
- Total: 44 images uploaded to Supabase Storage
- Typical duration: 5-30 seconds depending on complexity

**When to Use:**
- Design creation wizard
- Importing designs from templates
- API-based design management

**Authentication:** Requires business owner role + plan allowance

---

#### Update Design

Updates an existing design, optionally regenerating strips.

```
PUT /designs/{business_id}/{design_id}
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_id` | UUID | Yes | The business ID |
| `design_id` | UUID | Yes | The design ID |

**Request Body:** `CardDesignUpdate` (partial update - only include fields to change)
```json
{
    "background_color": "rgb(100, 50, 25)",
    "stamp_filled_color": "rgb(255, 200, 0)"
}
```

**Response:** `CardDesignResponse` (200 OK)

**Strip Regeneration Logic:**

| Design State | Strip-Affecting Change? | Behavior |
|--------------|------------------------|----------|
| Inactive | Yes | Synchronous regeneration (blocking) |
| Inactive | No | No regeneration |
| Active | Yes | Background regeneration + customer notifications |
| Active | No | No regeneration |

**Strip-Affecting Fields:**
- `background_color`
- `stamp_filled_color`
- `stamp_empty_color`
- `stamp_border_color`
- `total_stamps`
- `stamp_icon`
- `reward_icon`
- `icon_color`

**When to Use:**
- Design editor save button
- Bulk design updates
- A/B testing different designs

**Authentication:** Requires business owner role

---

#### Activate Design

Sets a design as the active design for the business.

```
POST /designs/{business_id}/{design_id}/activate
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_id` | UUID | Yes | The business ID |
| `design_id` | UUID | Yes | The design ID |

**Request Body:** None

**Response:** `CardDesignResponse` (200 OK)

**Behavior:**
1. Deactivates current active design (if any)
2. Activates the specified design
3. Verifies strip images exist (generates if missing)
4. Updates Google Wallet class with new design
5. Schedules background task to notify all customers:
   - Apple: Sends APNs push to all registered devices
   - Google: Updates all registered objects via API

**When to Use:**
- Switching between seasonal designs
- A/B testing different designs
- Launching new loyalty program

**Authentication:** Requires business owner role

---

#### Delete Design

Deletes a design and all associated assets.

```
DELETE /designs/{business_id}/{design_id}
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_id` | UUID | Yes | The business ID |
| `design_id` | UUID | Yes | The design ID |

**Response:** (200 OK)
```json
{
    "message": "Design deleted"
}
```

**Cleanup Operations:**
1. Deletes card assets from Supabase Storage (logo, stamps, background)
2. Deletes strip images from Supabase Storage
3. Deletes strip image records from database
4. Deletes design record from database

**Error Responses:**
| Status | Description |
|--------|-------------|
| 400 | Cannot delete active design |
| 404 | Design not found |

**When to Use:**
- Cleaning up unused designs
- Design management housekeeping

**Authentication:** Requires business owner role

---

#### Upload Design Assets

Upload logo, custom stamps, or strip background images.

```
POST /designs/{business_id}/{design_id}/upload/logo
POST /designs/{business_id}/{design_id}/upload/stamp/{stamp_type}
POST /designs/{business_id}/{design_id}/upload/strip-background
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_id` | UUID | Yes | The business ID |
| `design_id` | UUID | Yes | The design ID |
| `stamp_type` | String | For stamps | "filled" or "empty" |

**Request Body:** `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `file` | File | Image file (PNG recommended) |

**Response:** `UploadResponse` (200 OK)
```json
{
    "id": "design-uuid",
    "asset_type": "logo",
    "url": "https://supabase.storage.../logo.png",
    "filename": "logo.png"
}
```

**When to Use:**
- Design editor image uploads
- Bulk asset migration

**Authentication:** Requires business owner role

---

### Pass Endpoints

#### Download Apple Wallet Pass

Generates and downloads a .pkpass file for a customer.

```
GET /passes/{customer_id}
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `customer_id` | UUID | Yes | The customer ID |

**Response:** Binary `.pkpass` file (200 OK)
```
Content-Type: application/vnd.apple.pkpass
Content-Disposition: attachment; filename="pass.pkpass"
```

**Headers Returned:**
| Header | Description |
|--------|-------------|
| `Last-Modified` | RFC 7231 formatted timestamp |

**Behavior:**
1. Validates customer exists
2. Gets active design for customer's business
3. Generates .pkpass file with:
   - Customer name and stamp count
   - Business branding from design
   - QR code with customer ID
   - Strip image with visual stamps
   - Auth token for pass updates
4. Signs with Apple certificates

**When to Use:**
- "Add to Apple Wallet" button click
- Email with pass attachment
- Customer self-service portal

**Authentication:** None (public endpoint)

---

### Apple Wallet Endpoints

These endpoints are called by Apple Wallet, not by your application.

#### Register Device

Called by Apple Wallet when a pass is added to a device.

```
POST /wallet/v1/devices/{device_library_id}/registrations/{pass_type_id}/{serial_number}
```

**Request Body:**
```json
{
    "pushToken": "abc123..."
}
```

**Response:** 201 Created (no body)

**Behavior:**
- Validates auth token in Authorization header
- Creates registration in `push_registrations` table with `wallet_type = 'apple'`

---

#### Unregister Device

Called by Apple Wallet when a pass is removed from a device.

```
DELETE /wallet/v1/devices/{device_library_id}/registrations/{pass_type_id}/{serial_number}
```

**Response:** 200 OK (no body)

---

#### Get Updatable Passes

Called by Apple Wallet to check for pass updates.

```
GET /wallet/v1/devices/{device_library_id}/registrations/{pass_type_id}
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `passesUpdatedSince` | String | Unix timestamp filter |

**Response:** (200 OK)
```json
{
    "serialNumbers": ["customer-id-1", "customer-id-2"],
    "lastUpdated": "1705312200"
}
```

---

#### Get Latest Pass

Called by Apple Wallet to download updated pass.

```
GET /wallet/v1/passes/{pass_type_id}/{serial_number}
```

**Headers:**
| Header | Description |
|--------|-------------|
| `Authorization` | ApplePass {auth_token} |
| `If-Modified-Since` | RFC 7231 date for conditional request |

**Response:**
- 200 OK: Returns .pkpass file
- 304 Not Modified: Pass hasn't changed

---

#### Log Endpoint

Receives error logs from Apple Wallet.

```
POST /wallet/v1/log
```

**Request Body:**
```json
{
    "logs": ["Error message 1", "Error message 2"]
}
```

**Response:** 200 OK

---

### Google Wallet Endpoints

#### Callback Endpoint

Receives callbacks from Google Wallet when passes are saved or deleted.

```
POST /google-wallet/callback
```

**Request Body (from Google):**
```json
{
    "eventType": "save",
    "classId": "3388000000023082278.business-uuid",
    "objectId": "3388000000023082278.customer-uuid",
    "nonce": "unique-callback-id",
    "expTimeMillis": 1705312200000
}
```

**Event Types:**
| Type | Description |
|------|-------------|
| `save` | User added pass to Google Wallet |
| `del` | User removed pass from Google Wallet |

**Response:** (200 OK)
```json
{
    "status": "ok",
    "result": {
        "action": "save",
        "customer_id": "customer-uuid",
        "object_id": "3388000000023082278.customer-uuid",
        "class_id": "3388000000023082278.business-uuid",
        "registered": true
    }
}
```

**Nonce Deduplication:**
- First callback with nonce: processed and stored
- Duplicate callbacks with same nonce: acknowledged but not reprocessed

**When to Use:**
- This endpoint is called by Google, not your application
- Configure callback URL in Google Wallet class

---

#### Callback Verification

Google may call this to verify the callback URL is reachable.

```
GET /google-wallet/callback
```

**Response:** (200 OK)
```json
{
    "status": "ok",
    "service": "google-wallet-callback"
}
```

---

## Response Schemas

### CustomerResponse

```typescript
interface CustomerResponse {
    id: string;                    // UUID
    name: string;                  // Customer display name
    email: string;                 // Customer email
    stamps: number;                // Current stamp count (0 to total_stamps)
    pass_url: string | null;       // Apple Wallet pass download URL
    google_wallet_url: string | null; // Google Wallet JWT save URL
    created_at: string | null;     // ISO 8601 timestamp
    updated_at: string | null;     // ISO 8601 timestamp
}
```

### StampResponse

```typescript
interface StampResponse {
    customer_id: string;  // UUID
    name: string;         // Customer display name
    stamps: number;       // New stamp count after operation
    message: string;      // User-friendly status message
}
```

### CardDesignResponse

```typescript
interface CardDesignResponse {
    id: string;                           // UUID
    name: string;                         // Design name
    is_active: boolean;                   // Whether this is the active design
    organization_name: string;            // Business name on pass
    description: string;                  // Reward description
    logo_text: string | null;             // Fallback text if no logo image
    foreground_color: string;             // RGB string, e.g., "rgb(255, 255, 255)"
    background_color: string;             // RGB string
    label_color: string;                  // RGB string
    total_stamps: number;                 // Number of stamps needed for reward
    stamp_filled_color: string;           // RGB string
    stamp_empty_color: string;            // RGB string
    stamp_border_color: string;           // RGB string
    stamp_icon: string;                   // Icon name, e.g., "coffee", "star"
    reward_icon: string;                  // Icon name for final stamp
    icon_color: string;                   // Hex color, e.g., "#ffffff"
    logo_url: string | null;              // Supabase Storage URL
    custom_filled_stamp_url: string | null;
    custom_empty_stamp_url: string | null;
    strip_background_url: string | null;
    secondary_fields: PassField[];        // Apple Wallet secondary fields
    auxiliary_fields: PassField[];        // Apple Wallet auxiliary fields
    back_fields: PassField[];             // Apple Wallet back fields
    created_at: string | null;
    updated_at: string | null;
}

interface PassField {
    key: string;
    label: string;
    value: string;
}
```

### UploadResponse

```typescript
interface UploadResponse {
    id: string;          // Design UUID
    asset_type: string;  // "logo", "stamp_filled", "stamp_empty", "strip_background"
    url: string;         // Supabase Storage public URL
    filename: string;    // Stored filename
}
```

---

## Authentication

### API Authentication

Most endpoints require authentication via Supabase JWT:

```
Authorization: Bearer <supabase_jwt_token>
```

**Permission Levels:**

| Role | Can Do |
|------|--------|
| Scanner | Add stamps, redeem rewards, view customers |
| Admin | All scanner permissions + manage designs |
| Owner | All permissions |

### Apple Wallet Authentication

Apple Wallet uses pass-specific auth tokens:

```
Authorization: ApplePass <auth_token>
```

The auth token is:
- Generated when customer is created
- Stored in customer record
- Embedded in the .pkpass file
- Validated on all Apple Wallet API calls

### Google Wallet Authentication

No incoming authentication - Google Wallet callbacks are verified by:
1. Checking the nonce hasn't been processed before
2. Validating the object ID format matches expected pattern

Outgoing calls to Google Wallet API use service account credentials.

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Web Portal      │  Scanner App     │  Apple Wallet    │  Google Wallet    │
│  (Next.js)       │  (Expo)          │  (iOS)           │  (Android)        │
└────────┬─────────┴────────┬─────────┴────────┬─────────┴────────┬──────────┘
         │                  │                  │                  │
         ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Layer (FastAPI)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  /customers/*    │  /stamps/*       │  /wallet/*       │  /google-wallet/* │
│  /designs/*      │  /passes/*       │  (Apple)         │  (Google)         │
└────────┬─────────┴────────┬─────────┴────────┬─────────┴────────┬──────────┘
         │                  │                  │                  │
         └──────────────────┴──────────────────┴──────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Service Layer                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                         PassCoordinator                                      │
│                              │                                               │
│           ┌──────────────────┼──────────────────┐                           │
│           ▼                  ▼                  ▼                           │
│   AppleWalletService  GoogleWalletService  StripImageService                │
│         │                    │                  │                           │
│         ▼                    ▼                  ▼                           │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│   │PassGenerator│    │Google API   │    │StripGenerator│                   │
│   │APNsClient   │    │JWT Signing  │    │StorageService│                   │
│   └─────────────┘    └─────────────┘    └─────────────┘                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Repository Layer                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  CustomerRepository      │  WalletRegistrationRepository                    │
│  CardDesignRepository    │  StripImageRepository                            │
│  BusinessRepository      │  CallbackNonceRepository                         │
│  DeviceRepository        │                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Data Layer                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│              Supabase (PostgreSQL + Storage)                                │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  Tables:                      │  Storage Buckets:                │      │
│  │  - customers                  │  - businesses/                   │      │
│  │  - card_designs               │    └── {business_id}/            │      │
│  │  - businesses                 │        └── cards/{design_id}/    │      │
│  │  - push_registrations         │            ├── logo.png          │      │
│  │  - strip_images               │            └── strips/           │      │
│  │  - google_callback_nonces     │                ├── apple/        │      │
│  │                               │                └── google/       │      │
│  └──────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Customer Registration

```
Web Portal                API                    Services                External
    │                      │                        │                       │
    │  POST /customers     │                        │                       │
    │─────────────────────>│                        │                       │
    │                      │                        │                       │
    │                      │  CustomerRepository    │                       │
    │                      │  .create()             │                       │
    │                      │───────────────────────>│                       │
    │                      │<───────────────────────│                       │
    │                      │                        │                       │
    │                      │  coordinator           │                       │
    │                      │  .on_customer_created()│                       │
    │                      │───────────────────────>│                       │
    │                      │                        │                       │
    │                      │                        │  Apple: get_pass_url()│
    │                      │                        │─────────────────────>│
    │                      │                        │<─────────────────────│
    │                      │                        │                       │
    │                      │                        │  Google: JWT sign     │
    │                      │                        │  generate_save_url()  │
    │                      │                        │─────────────────────>│
    │                      │                        │<─────────────────────│
    │                      │                        │                       │
    │                      │<───────────────────────│                       │
    │                      │                        │                       │
    │  {customer,          │                        │                       │
    │   pass_url,          │                        │                       │
    │   google_wallet_url} │                        │                       │
    │<─────────────────────│                        │                       │
```

### Data Flow: Stamp Addition

```
Scanner App            API                  Services              Apple/Google
    │                   │                      │                       │
    │ POST /stamps      │                      │                       │
    │──────────────────>│                      │                       │
    │                   │                      │                       │
    │                   │ CustomerRepository   │                       │
    │                   │ .add_stamp()         │                       │
    │                   │─────────────────────>│                       │
    │                   │<─────────────────────│                       │
    │                   │                      │                       │
    │                   │ coordinator          │                       │
    │                   │ .on_stamp_added()    │                       │
    │                   │─────────────────────>│                       │
    │                   │                      │                       │
    │                   │                      │ [If Apple registered] │
    │                   │                      │ APNs push             │
    │                   │                      │─────────────────────>│
    │                   │                      │                 APNs │
    │                   │                      │                       │
    │                   │                      │ [If Google registered]│
    │                   │                      │ PATCH object          │
    │                   │                      │─────────────────────>│
    │                   │                      │           Google API │
    │                   │                      │<─────────────────────│
    │                   │                      │                       │
    │                   │<─────────────────────│                       │
    │                   │                      │                       │
    │ {stamps, message} │                      │                       │
    │<──────────────────│                      │                       │
```

---

## Service Layer API

### PassCoordinator

The main orchestrator for wallet operations.

**Import:**
```python
from app.services.wallets import PassCoordinator, create_pass_coordinator
```

**Factory Function:**
```python
coordinator = create_pass_coordinator()
```

**Methods:**

#### get_wallet_urls

```python
def get_wallet_urls(
    self,
    customer: dict,
    business: dict,
    design: dict,
) -> dict:
    """
    Get wallet save URLs for both platforms.

    Args:
        customer: Customer dict with id, name, stamps, auth_token
        business: Business dict with id, name
        design: Card design dict

    Returns:
        {
            "apple_url": "https://api.example.com/passes/{customer_id}",
            "google_url": "https://pay.google.com/gp/v/save/{jwt}"
        }
    """
```

#### on_customer_created

```python
def on_customer_created(
    self,
    customer: dict,
    business: dict,
    design: dict,
) -> dict:
    """
    Handle customer creation - generate wallet URLs.

    Alias for get_wallet_urls(), semantically named for the creation flow.
    """
```

#### on_stamp_added

```python
async def on_stamp_added(
    self,
    customer: dict,
    business: dict,
    design: dict,
) -> dict:
    """
    Handle stamp addition - update both wallets.

    Args:
        customer: Customer dict with updated stamp count
        business: Business dict
        design: Active card design dict

    Returns:
        {
            "apple": {"success": 1, "failed": 0},
            "google": {"success": True}
        }

    Behavior:
        - Apple: Sends APNs push to all registered devices
        - Google: Updates object via PATCH API call
    """
```

#### on_design_updated

```python
async def on_design_updated(
    self,
    business: dict,
    design: dict,
    regenerate_strips: bool = True,
) -> dict:
    """
    Handle design update - regenerate strips and notify customers.

    Args:
        business: Business dict
        design: Updated design dict
        regenerate_strips: Whether to regenerate strip images

    Returns:
        {
            "strips_regenerated": True,
            "google_class_updated": True,
            "apple_notifications": {"success": 10, "failed": 0},
            "google_objects_updated": 5
        }
    """
```

#### on_design_activated

```python
def on_design_activated(
    self,
    business: dict,
    design: dict,
) -> dict:
    """
    Handle design activation.

    Args:
        business: Business dict
        design: Activated design dict

    Returns:
        {
            "google_class_updated": True,
            "strips_exist": True
        }

    Note: Strips should already exist from creation.
    """
```

#### pregenerate_strips_for_design

```python
def pregenerate_strips_for_design(
    self,
    design: dict,
    business_id: str,
) -> dict:
    """
    Pre-generate strip images for a design.

    Args:
        design: Design dict
        business_id: Business UUID

    Returns:
        {
            "apple": ["url1", "url2", ...],
            "google": ["url1", "url2", ...]
        }

    Performance:
        - Generates (total_stamps + 1) × 4 images
        - Typical time: 5-30 seconds
        - Called synchronously on design creation
    """
```

---

### GoogleWalletService

Handles Google Wallet API interactions.

**Import:**
```python
from app.services.wallets import GoogleWalletService, create_google_wallet_service
```

**Methods:**

#### generate_save_url

```python
def generate_save_url(
    self,
    customer: dict,
    business: dict,
    design: dict,
    stamp_count: int = 0,
) -> str:
    """
    Generate JWT-signed save URL.

    Args:
        customer: Customer dict
        business: Business dict
        design: Design dict
        stamp_count: Current stamp count

    Returns:
        "https://pay.google.com/gp/v/save/eyJhbGciOiJSUzI1NiI..."

    Note: URL can be used directly as href on "Add to Google Wallet" button.
    """
```

#### create_or_update_class

```python
def create_or_update_class(
    self,
    business: dict,
    design: dict,
) -> str:
    """
    Create or update GenericClass for a business.

    Args:
        business: Business dict
        design: Design dict

    Returns:
        Class ID string (e.g., "3388000000023082278.business-uuid")
    """
```

#### update_object

```python
def update_object(
    self,
    customer: dict,
    business: dict,
    design: dict,
    stamp_count: int,
) -> str:
    """
    Update existing GenericObject with new stamp count.

    Args:
        customer: Customer dict
        business: Business dict
        design: Design dict
        stamp_count: New stamp count

    Returns:
        Object ID string

    Behavior:
        - Gets new hero image URL from strip_images table
        - Updates object via PATCH API call
        - If object doesn't exist, creates it
    """
```

---

### AppleWalletService

Wraps Apple Wallet functionality.

**Import:**
```python
from app.services.wallets import AppleWalletService, create_apple_wallet_service
```

**Methods:**

#### get_pass_url

```python
def get_pass_url(self, customer: dict) -> str:
    """
    Get pass download URL.

    Args:
        customer: Customer dict with id

    Returns:
        "https://api.example.com/passes/{customer_id}"
    """
```

#### send_update

```python
async def send_update(self, customer_id: str) -> dict:
    """
    Send push notifications to update a customer's pass.

    Args:
        customer_id: Customer UUID

    Returns:
        {"success": 2, "failed": 0}

    Behavior:
        - Gets all Apple push tokens for customer
        - Sends empty APNs push to each device
        - Device fetches updated pass from /wallet/v1/passes/...
    """
```

---

### StripImageService

Pre-generates and manages strip images.

**Import:**
```python
from app.services.wallets import StripImageService, create_strip_image_service
```

**Methods:**

#### pregenerate_all_strips

```python
def pregenerate_all_strips(
    self,
    design: dict,
    business_id: str,
) -> dict[str, list[str]]:
    """
    Pre-generate all strip images for a design.

    Args:
        design: Design dict
        business_id: Business UUID

    Returns:
        {
            "apple": ["url_0_1x", "url_0_2x", "url_0_3x", ...],
            "google": ["hero_0_url", "hero_1_url", ...]
        }

    Generated Images:
        - Apple: 3 resolutions per stamp count
        - Google: 1 hero image per stamp count
        - Total: (total_stamps + 1) × 4 images
    """
```

#### get_strip_url

```python
def get_strip_url(
    self,
    design_id: str,
    stamp_count: int,
    platform: Literal["apple", "google"],
    resolution: str = "3x",
) -> str | None:
    """
    Get pre-generated strip URL from database.

    Args:
        design_id: Design UUID
        stamp_count: Number of filled stamps
        platform: "apple" or "google"
        resolution: "1x", "2x", "3x" for Apple; "hero" for Google

    Returns:
        Supabase Storage URL or None if not found
    """
```

---

## Repository Layer API

### WalletRegistrationRepository

Manages wallet registrations across platforms.

**Import:**
```python
from app.repositories.wallet_registration import WalletRegistrationRepository
```

**Key Methods:**

```python
# Check if customer has wallet registrations
WalletRegistrationRepository.has_apple_wallet(customer_id: str) -> bool
WalletRegistrationRepository.has_google_wallet(customer_id: str) -> bool

# Get registrations
WalletRegistrationRepository.get_apple_tokens(customer_id: str) -> list[str]
WalletRegistrationRepository.get_google_registrations(customer_id: str) -> list[dict]

# Register/unregister (called by callbacks)
WalletRegistrationRepository.register_google(customer_id: str, google_object_id: str) -> None
WalletRegistrationRepository.unregister_google(customer_id: str, google_object_id: str) -> None

# Business-wide queries
WalletRegistrationRepository.get_all_apple_for_business(business_id: str) -> list[dict]
WalletRegistrationRepository.get_all_google_for_business(business_id: str) -> list[dict]
```

### StripImageRepository

Manages pre-generated strip image URLs.

**Import:**
```python
from app.repositories.strip_image import StripImageRepository
```

**Key Methods:**

```python
# Get URLs
StripImageRepository.get_url(design_id, stamp_count, platform, resolution) -> str | None
StripImageRepository.get_apple_urls(design_id, stamp_count) -> dict[str, str]
StripImageRepository.get_google_hero_url(design_id, stamp_count) -> str | None

# Store URLs
StripImageRepository.upsert(design_id, stamp_count, platform, resolution, url) -> dict
StripImageRepository.upsert_batch(records: list[dict]) -> None

# Cleanup
StripImageRepository.delete_for_design(design_id: str) -> int
StripImageRepository.exists_for_design(design_id: str) -> bool
```

---

## Usage Examples

### Frontend: Add to Wallet Buttons

```tsx
// React/Next.js example
function WalletButtons({ customer }) {
    return (
        <div className="wallet-buttons">
            {/* Apple Wallet - direct link */}
            <a href={customer.pass_url} className="apple-wallet-btn">
                <img src="/apple-wallet-badge.svg" alt="Add to Apple Wallet" />
            </a>

            {/* Google Wallet - direct link */}
            {customer.google_wallet_url && (
                <a href={customer.google_wallet_url} className="google-wallet-btn">
                    <img src="/google-wallet-badge.svg" alt="Add to Google Wallet" />
                </a>
            )}
        </div>
    );
}
```

### Backend: Custom Stamp Logic

```python
from app.services.wallets import create_pass_coordinator
from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.repositories.business import BusinessRepository

async def add_stamps_for_purchase(customer_id: str, purchase_amount: float):
    """Add stamps based on purchase amount."""
    customer = CustomerRepository.get_by_id(customer_id)
    business = BusinessRepository.get_by_id(customer["business_id"])
    design = CardDesignRepository.get_active(customer["business_id"])

    # Calculate stamps (1 stamp per $10)
    stamps_to_add = int(purchase_amount / 10)

    for _ in range(stamps_to_add):
        new_stamps = CustomerRepository.add_stamp(
            customer_id,
            design["total_stamps"]
        )

        # Update customer dict for wallet update
        customer["stamps"] = new_stamps

    # Update wallets once at the end
    coordinator = create_pass_coordinator()
    await coordinator.on_stamp_added(customer, business, design)

    return customer["stamps"]
```

### Backend: Bulk Design Migration

```python
from app.services.wallets import create_pass_coordinator
from app.repositories.card_design import CardDesignRepository
from app.repositories.business import BusinessRepository

async def migrate_all_designs_to_new_branding(business_id: str, new_colors: dict):
    """Update all designs with new brand colors."""
    coordinator = create_pass_coordinator()
    business = BusinessRepository.get_by_id(business_id)
    designs = CardDesignRepository.get_all(business_id)

    for design in designs:
        # Update design
        updated_design = CardDesignRepository.update(
            design["id"],
            **new_colors
        )

        # Regenerate strips
        coordinator.pregenerate_strips_for_design(updated_design, business_id)

        # If active, notify all customers
        if design["is_active"]:
            await coordinator.on_design_updated(
                business=business,
                design=updated_design,
                regenerate_strips=False  # Already regenerated above
            )
```

---

## Error Handling

### API Error Responses

All endpoints return standard HTTP error responses:

```json
{
    "detail": "Error message here"
}
```

**Common Error Codes:**

| Status | Meaning |
|--------|---------|
| 400 | Bad request (validation error, business logic error) |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not found (resource doesn't exist) |
| 500 | Internal server error |

### Graceful Degradation

Wallet operations are designed to fail gracefully:

```python
# Example from stamps.py
try:
    await coordinator.on_stamp_added(customer, business, design)
except Exception as e:
    print(f"Wallet update error: {e}")
    # Stamp still added - wallet update failure is non-fatal
```

**Degradation Hierarchy:**
1. Stamp/core operation always succeeds if possible
2. Apple Wallet update failure: logged, not raised
3. Google Wallet update failure: logged, not raised
4. Strip generation failure: logged, design still created

### Retry Behavior

| Operation | Retry Policy |
|-----------|--------------|
| Database operations | Automatic via `@with_retry()` decorator |
| APNs push | No automatic retry (handled by APNs) |
| Google API calls | No automatic retry (idempotent operations) |
| Storage uploads | Manual retry on failure |

### Monitoring Recommendations

Log messages to monitor:

```
Wallet update error: {e}
Strip pre-generation error: {e}
Wallet URL generation error: {e}
Background design update error: {e}
Customer notification error: {e}
Google Wallet callback error: {e}
```

Set up alerts for:
- High frequency of wallet update errors
- Strip generation failures
- Google API authentication failures
- Callback processing failures
