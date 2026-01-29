import time

from fastapi import APIRouter, HTTPException, Header, Body, Response, Depends

from app.repositories.customer import CustomerRepository
from app.repositories.device import DeviceRepository
from app.services.pass_generator import PassGenerator
from app.core.security import verify_auth_token
from app.api.deps import get_pass_generator

router = APIRouter()


@router.post("/v1/devices/{device_library_id}/registrations/{pass_type_id}/{serial_number}")
def register_device_endpoint(
    device_library_id: str,
    pass_type_id: str,
    serial_number: str,
    authorization: str | None = Header(None),
    body: dict = Body(...),
):
    """Register a device for push notifications."""
    auth_token = verify_auth_token(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization required")

    customer = CustomerRepository.get_by_auth_token(serial_number, auth_token)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    push_token = body.get("pushToken")
    if not push_token:
        raise HTTPException(status_code=400, detail="pushToken required")

    DeviceRepository.register(serial_number, device_library_id, push_token)

    print(f"Device registered: {device_library_id[:20]}... for customer {serial_number[:8]}...")

    return Response(status_code=201)


@router.delete("/v1/devices/{device_library_id}/registrations/{pass_type_id}/{serial_number}")
def unregister_device_endpoint(
    device_library_id: str,
    pass_type_id: str,
    serial_number: str,
    authorization: str | None = Header(None),
):
    """Unregister a device from push notifications."""
    auth_token = verify_auth_token(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization required")

    customer = CustomerRepository.get_by_auth_token(serial_number, auth_token)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    DeviceRepository.unregister(serial_number, device_library_id)

    print(f"Device unregistered: {device_library_id[:20]}... for customer {serial_number[:8]}...")

    return Response(status_code=200)


@router.get("/v1/devices/{device_library_id}/registrations/{pass_type_id}")
def get_serial_numbers(
    device_library_id: str,
    pass_type_id: str,
    passesUpdatedSince: str | None = None,
):
    """Get list of passes registered to this device that have been updated."""
    serial_numbers = DeviceRepository.get_serial_numbers_for_device(device_library_id)

    if not serial_numbers:
        return Response(status_code=204)

    return {
        "serialNumbers": serial_numbers,
        "lastUpdated": str(int(time.time())),
    }


@router.get("/v1/passes/{pass_type_id}/{serial_number}")
def get_latest_pass(
    pass_type_id: str,
    serial_number: str,
    authorization: str | None = Header(None),
    pass_generator: PassGenerator = Depends(get_pass_generator),
):
    """Download the latest version of a pass."""
    auth_token = verify_auth_token(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization required")

    customer = CustomerRepository.get_by_auth_token(serial_number, auth_token)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    pass_data = pass_generator.generate_pass(
        customer_id=customer["id"],
        name=customer["name"],
        stamps=customer["stamps"],
        auth_token=customer["auth_token"],
        business_id=customer.get("business_id"),
    )

    return Response(
        content=pass_data,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Last-Modified": str(customer.get("updated_at", "")),
        },
    )


@router.post("/v1/log")
def receive_logs(body: dict = Body(...)):
    """Receive error logs from Apple Wallet."""
    logs = body.get("logs", [])
    for log in logs:
        print(f"Wallet log: {log}")
    return Response(status_code=200)
