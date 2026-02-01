import time
from datetime import datetime, timezone
from email.utils import formatdate, parsedate_to_datetime

from fastapi import APIRouter, HTTPException, Header, Body, Response, Depends

from app.repositories.customer import CustomerRepository
from app.repositories.device import DeviceRepository
from app.repositories.card_design import CardDesignRepository
from app.services.pass_generator import PassGenerator
from app.core.security import verify_auth_token
from app.api.deps import get_pass_generator


def _parse_datetime(dt_value) -> datetime | None:
    """Parse a datetime value from the database (could be string or datetime)."""
    if dt_value is None:
        return None
    if isinstance(dt_value, datetime):
        if dt_value.tzinfo is None:
            return dt_value.replace(tzinfo=timezone.utc)
        return dt_value
    if isinstance(dt_value, str):
        try:
            # Handle ISO format with timezone
            dt = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


def _get_last_modified(customer: dict, design: dict | None) -> datetime | None:
    """Get the latest modification time between customer and design."""
    customer_updated = _parse_datetime(customer.get("updated_at"))
    design_updated = _parse_datetime(design.get("updated_at")) if design else None

    timestamps = [t for t in [customer_updated, design_updated] if t is not None]
    return max(timestamps) if timestamps else None

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
    passesUpdatedSince: str | None = None,  # noqa: N803 - Apple Wallet API requirement
):
    """Get list of passes registered to this device that have been updated."""
    serial_numbers = DeviceRepository.get_serial_numbers_for_device(device_library_id)

    if not serial_numbers:
        return Response(status_code=204)

    # Filter by passesUpdatedSince if provided
    if passesUpdatedSince:
        try:
            since_timestamp = float(passesUpdatedSince)
            since_dt = datetime.fromtimestamp(since_timestamp, tz=timezone.utc)

            filtered = []
            for serial_number in serial_numbers:
                customer = CustomerRepository.get_by_id(serial_number)
                if customer:
                    design = CardDesignRepository.get_active(customer.get("business_id"))
                    last_modified = _get_last_modified(customer, design)

                    # Include if modified after the given timestamp
                    if last_modified and last_modified > since_dt:
                        filtered.append(serial_number)

            serial_numbers = filtered
        except (ValueError, TypeError):
            pass  # Invalid timestamp, return all passes

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
    if_modified_since: str | None = Header(None, alias="If-Modified-Since"),
    pass_generator: PassGenerator = Depends(get_pass_generator),
):
    """Download the latest version of a pass."""
    auth_token = verify_auth_token(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization required")

    customer = CustomerRepository.get_by_auth_token(serial_number, auth_token)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # Get the active design to check its updated_at
    design = CardDesignRepository.get_active(customer.get("business_id"))

    # Determine latest modification time (max of customer and design)
    last_modified = _get_last_modified(customer, design)

    # Check If-Modified-Since header - return 304 if pass hasn't changed
    if if_modified_since and last_modified:
        try:
            client_date = parsedate_to_datetime(if_modified_since)
            # Make sure client_date is timezone-aware for comparison
            if client_date.tzinfo is None:
                client_date = client_date.replace(tzinfo=timezone.utc)
            if last_modified <= client_date:
                return Response(status_code=304)  # Not Modified
        except (ValueError, TypeError):
            pass  # Invalid header format, continue with full response

    pass_data = pass_generator.generate_pass(
        customer_id=customer["id"],
        name=customer["name"],
        stamps=customer["stamps"],
        auth_token=customer["auth_token"],
        business_id=customer.get("business_id"),
    )

    # Format Last-Modified header properly (RFC 7231)
    last_modified_header = ""
    if last_modified:
        last_modified_header = formatdate(last_modified.timestamp(), usegmt=True)

    return Response(
        content=pass_data,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Last-Modified": last_modified_header,
        },
    )


@router.post("/v1/log")
def receive_logs(body: dict = Body(...)):
    """Receive error logs from Apple Wallet."""
    logs = body.get("logs", [])
    for log in logs:
        print(f"Wallet log: {log}")
    return Response(status_code=200)
