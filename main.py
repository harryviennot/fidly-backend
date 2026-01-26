import os
import uuid
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv
import io

load_dotenv()

from database import (
    init_db,
    create_customer,
    get_customer,
    get_customer_by_email,
    get_all_customers,
    add_stamp,
    register_device,
    unregister_device,
    get_push_tokens,
    get_customer_by_auth_token,
)
from models import CustomerCreate, CustomerResponse, StampResponse, DeviceRegistration
from pass_generator import create_pass_generator
from apns import create_apns_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title="Loyalty Card POC",
    description="Apple Wallet Loyalty Card API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for web app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
pass_generator = create_pass_generator()
apns_client = create_apns_client()

BASE_URL = os.getenv("BASE_URL", "https://762bfadc669f.ngrok-free.app")
PASS_TYPE_ID = os.getenv("APPLE_PASS_TYPE_ID", "")


# ============ Customer Endpoints ============

@app.post("/customers", response_model=CustomerResponse)
async def create_new_customer(customer: CustomerCreate):
    """Create a new customer and return their info with pass URL."""
    # Check if email already exists
    existing = await get_customer_by_email(customer.email)
    if existing:
        return CustomerResponse(
            id=existing["id"],
            name=existing["name"],
            email=existing["email"],
            stamps=existing["stamps"],
            pass_url=f"{BASE_URL}/passes/{existing['id']}",
        )

    # Create new customer
    customer_id = str(uuid.uuid4())
    auth_token = secrets.token_hex(16)  # 32 character token

    result = await create_customer(customer_id, customer.name, customer.email, auth_token)

    return CustomerResponse(
        id=result["id"],
        name=result["name"],
        email=result["email"],
        stamps=result["stamps"],
        pass_url=f"{BASE_URL}/passes/{result['id']}",
    )


@app.get("/customers", response_model=list[CustomerResponse])
async def list_customers():
    """Get all customers."""
    customers = await get_all_customers()
    return [
        CustomerResponse(
            id=c["id"],
            name=c["name"],
            email=c["email"],
            stamps=c["stamps"],
            pass_url=f"{BASE_URL}/passes/{c['id']}",
        )
        for c in customers
    ]


@app.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer_info(customer_id: str):
    """Get customer details."""
    customer = await get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerResponse(
        id=customer["id"],
        name=customer["name"],
        email=customer["email"],
        stamps=customer["stamps"],
        pass_url=f"{BASE_URL}/passes/{customer['id']}",
    )


# ============ Pass Endpoints ============

@app.get("/passes/{customer_id}")
async def download_pass(customer_id: str):
    """Download the .pkpass file for a customer."""
    customer = await get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    pass_data = pass_generator.generate_pass(
        customer_id=customer["id"],
        name=customer["name"],
        stamps=customer["stamps"],
        auth_token=customer["auth_token"],
    )

    # Sanitize filename for HTTP header (ASCII only)
    safe_name = customer["name"].encode("ascii", "ignore").decode("ascii").replace('"', "")
    if not safe_name:
        safe_name = "loyalty-card"

    return Response(
        content=pass_data,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}-loyalty.pkpass"',
        },
    )


# ============ Stamp Endpoint ============

@app.post("/stamps/{customer_id}", response_model=StampResponse)
async def add_customer_stamp(customer_id: str):
    """Add a stamp to a customer and trigger push notification."""
    customer = await get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer["stamps"] >= 10:
        return StampResponse(
            customer_id=customer_id,
            name=customer["name"],
            stamps=10,
            message="Already at maximum stamps! Ready for reward.",
        )

    new_stamps = await add_stamp(customer_id)

    # Send push notification to all registered devices
    push_tokens = await get_push_tokens(customer_id)
    if push_tokens:
        await apns_client.send_to_all_devices(push_tokens)

    message = "Stamp added!"
    if new_stamps == 10:
        message = "Congratulations! You've earned a free coffee!"

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=new_stamps,
        message=message,
    )


# ============ Apple Wallet Web Service Endpoints ============

def verify_auth_token(authorization: str | None) -> str | None:
    """Extract auth token from Authorization header."""
    if not authorization:
        return None
    if authorization.startswith("ApplePass "):
        return authorization[10:]
    return None


@app.post("/wallet/v1/devices/{device_library_id}/registrations/{pass_type_id}/{serial_number}")
async def register_device_endpoint(
    device_library_id: str,
    pass_type_id: str,
    serial_number: str,
    authorization: str | None = Header(None),
    body: dict = Body(...),
):
    """
    Register a device for push notifications.
    Called by Apple Wallet when a pass is added to a device.
    """
    auth_token = verify_auth_token(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization required")

    # Verify the auth token matches the customer
    customer = await get_customer_by_auth_token(serial_number, auth_token)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    push_token = body.get("pushToken")
    if not push_token:
        raise HTTPException(status_code=400, detail="pushToken required")

    # Register the device
    registration_id = str(uuid.uuid4())
    await register_device(registration_id, serial_number, device_library_id, push_token)

    print(f"Device registered: {device_library_id[:20]}... for customer {serial_number[:8]}...")

    # Return 201 for new registration, 200 for update
    return Response(status_code=201)


@app.delete("/wallet/v1/devices/{device_library_id}/registrations/{pass_type_id}/{serial_number}")
async def unregister_device_endpoint(
    device_library_id: str,
    pass_type_id: str,
    serial_number: str,
    authorization: str | None = Header(None),
):
    """
    Unregister a device from push notifications.
    Called by Apple Wallet when a pass is removed from a device.
    """
    auth_token = verify_auth_token(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization required")

    customer = await get_customer_by_auth_token(serial_number, auth_token)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    await unregister_device(serial_number, device_library_id)

    print(f"Device unregistered: {device_library_id[:20]}... for customer {serial_number[:8]}...")

    return Response(status_code=200)


@app.get("/wallet/v1/devices/{device_library_id}/registrations/{pass_type_id}")
async def get_serial_numbers(
    device_library_id: str,
    pass_type_id: str,
    passesUpdatedSince: str | None = None,
):
    """
    Get list of passes registered to this device that have been updated.
    Called by Apple Wallet after receiving a push notification.
    """
    # For POC, we return all serial numbers for this device
    # In production, you'd filter by passesUpdatedSince timestamp
    from database import get_db

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT customer_id FROM push_registrations WHERE device_library_id = ?",
            (device_library_id,)
        )
        rows = await cursor.fetchall()

    if not rows:
        return Response(status_code=204)  # No content

    serial_numbers = [row["customer_id"] for row in rows]

    return {
        "serialNumbers": serial_numbers,
        "lastUpdated": str(int(__import__("time").time())),
    }


@app.get("/wallet/v1/passes/{pass_type_id}/{serial_number}")
async def get_latest_pass(
    pass_type_id: str,
    serial_number: str,
    authorization: str | None = Header(None),
):
    """
    Download the latest version of a pass.
    Called by Apple Wallet after receiving notification of an update.
    """
    auth_token = verify_auth_token(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization required")

    customer = await get_customer_by_auth_token(serial_number, auth_token)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    pass_data = pass_generator.generate_pass(
        customer_id=customer["id"],
        name=customer["name"],
        stamps=customer["stamps"],
        auth_token=customer["auth_token"],
    )

    return Response(
        content=pass_data,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Last-Modified": str(customer.get("updated_at", "")),
        },
    )


@app.post("/wallet/v1/log")
async def receive_logs(body: dict = Body(...)):
    """Receive error logs from Apple Wallet (for debugging)."""
    logs = body.get("logs", [])
    for log in logs:
        print(f"Wallet log: {log}")
    return Response(status_code=200)


# ============ Health Check ============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "loyalty-card-poc"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
