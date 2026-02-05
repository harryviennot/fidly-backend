"""
Demo API routes for interactive landing page demo.
Completely separate from business routes.
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from email.utils import formatdate

from fastapi import APIRouter, HTTPException, Response, Header, Body, Request
from fastapi.responses import StreamingResponse

from app.repositories.demo import (
    DemoSessionRepository,
    DemoCustomerRepository,
    DemoDeviceRepository,
)
from app.services.demo_pass_generator import create_demo_pass_generator
from app.services.apns import APNsClient, create_demo_apns_client
from app.core.security import verify_auth_token


router = APIRouter()


# ============================================
# Session Management
# ============================================

@router.post("/sessions")
def create_demo_session():
    """Create a new demo session. Returns session token for QR code."""
    session = DemoSessionRepository.create()
    if not session:
        raise HTTPException(status_code=500, detail="Failed to create session")

    return {
        "session_id": session["id"],
        "session_token": session["session_token"],
        "status": session["status"],
        "stamps": session["stamps"],
        "expires_at": session["expires_at"],
    }


@router.get("/sessions/{session_token}")
def get_demo_session(session_token: str):
    """Get session status by token (for landing page polling/SSE)."""
    session = DemoSessionRepository.get_by_token(session_token)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Check if expired
    expires_at = session.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        else:
            exp_dt = expires_at
        if exp_dt < datetime.now(timezone.utc):
            raise HTTPException(status_code=404, detail="Session expired")

    return {
        "session_id": session["id"],
        "session_token": session["session_token"],
        "status": session["status"],
        "stamps": session["stamps"],
        "demo_customer_id": session.get("demo_customer_id"),
    }


@router.get("/sessions/{session_token}/events")
async def session_events(session_token: str, request: Request):
    """Server-Sent Events stream for session status updates."""
    session = DemoSessionRepository.get_by_token(session_token)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_stream():
        last_status = None
        last_stamps = -1

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            session = DemoSessionRepository.get_by_token(session_token)
            if not session:
                yield f"event: expired\ndata: {{}}\n\n"
                break

            # Check if expired
            expires_at = session.get("expires_at")
            if expires_at:
                if isinstance(expires_at, str):
                    exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                else:
                    exp_dt = expires_at
                if exp_dt < datetime.now(timezone.utc):
                    yield f"event: expired\ndata: {{}}\n\n"
                    break

            # Send update if status or stamps changed
            if session["status"] != last_status or session["stamps"] != last_stamps:
                last_status = session["status"]
                last_stamps = session["stamps"]
                data = json.dumps({
                    "status": session["status"],
                    "stamps": session["stamps"],
                })
                yield f"data: {data}\n\n"

            await asyncio.sleep(1)  # Poll every second

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# ============================================
# Pass Generation & Download
# ============================================

@router.get("/pass/{session_token}")
def get_demo_pass(session_token: str):
    """Generate and return demo pass for phone to download."""
    session = DemoSessionRepository.get_by_token(session_token)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Check if expired
    expires_at = session.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        else:
            exp_dt = expires_at
        if exp_dt < datetime.now(timezone.utc):
            raise HTTPException(status_code=404, detail="Session expired")

    # Create demo customer if doesn't exist
    if not session.get("demo_customer_id"):
        customer = DemoCustomerRepository.create(session["id"])
        if not customer:
            raise HTTPException(status_code=500, detail="Failed to create demo customer")

        # Link customer to session
        DemoSessionRepository.update_status(
            session["id"], "pass_downloaded", customer["id"]
        )
        customer_id = customer["id"]
        auth_token = customer["auth_token"]
        stamps = 0
    else:
        customer = DemoCustomerRepository.get_by_id(session["demo_customer_id"])
        if not customer:
            raise HTTPException(status_code=500, detail="Demo customer not found")
        customer_id = customer["id"]
        auth_token = customer["auth_token"]
        stamps = customer["stamps"]

    # Generate pass
    generator = create_demo_pass_generator()
    pass_data = generator.generate_demo_pass(
        customer_id=customer_id,
        stamps=stamps,
        auth_token=auth_token,
    )

    return Response(
        content=pass_data,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Content-Disposition": 'attachment; filename="stampeo-demo.pkpass"',
        }
    )


# ============================================
# Demo Stamping (called from landing page)
# ============================================

@router.post("/sessions/{session_token}/stamp")
async def add_demo_stamp(session_token: str):
    """Add a stamp to the demo session and push update to phone."""
    session = DemoSessionRepository.get_by_token(session_token)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] != "pass_installed":
        raise HTTPException(status_code=400, detail="Pass not yet installed")

    if session["stamps"] >= 8:
        return {"stamps": 8, "message": "Maximum stamps reached!"}

    # Add stamp to session
    new_stamps = DemoSessionRepository.add_stamp(session["id"])

    # Also update the customer record (for pass generation)
    if session.get("demo_customer_id"):
        DemoCustomerRepository.add_stamp(session["demo_customer_id"])

        # Send push notification to update the pass
        push_tokens = DemoDeviceRepository.get_push_tokens(session["demo_customer_id"])
        if push_tokens:
            apns_client = create_demo_apns_client()
            await apns_client.send_to_all_devices(push_tokens)

    return {"stamps": new_stamps, "message": "Stamp added!"}


# ============================================
# Apple Wallet Callbacks (separate from production)
# ============================================

async def schedule_followup_notification(
    demo_customer_id: str,
    push_tokens: list[str],
):
    """Schedule a follow-up notification 5 minutes after pass install."""
    await asyncio.sleep(300)  # 5 minutes

    # Get fresh push tokens in case they changed
    current_tokens = DemoDeviceRepository.get_push_tokens(demo_customer_id)
    if not current_tokens:
        return

    # Send push to trigger pass refresh
    # The updated pass will have the promotional message in backFields
    apns_client = create_demo_apns_client()
    await apns_client.send_to_all_devices(current_tokens)

    print(f"Follow-up notification sent for demo customer {demo_customer_id[:8]}...")


@router.post("/wallet/v1/devices/{device_library_id}/registrations/{pass_type_id}/{serial_number}")
async def register_demo_device(
    device_library_id: str,
    pass_type_id: str,
    serial_number: str,
    authorization: str | None = Header(None),
    body: dict = Body(...),
):
    """Register demo device for push notifications."""
    auth_token = verify_auth_token(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization required")

    customer = DemoCustomerRepository.get_by_auth_token(serial_number, auth_token)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    push_token = body.get("pushToken")
    if not push_token:
        raise HTTPException(status_code=400, detail="pushToken required")

    # Register device
    DemoDeviceRepository.register(serial_number, device_library_id, push_token)

    # Update session status to "pass_installed"
    session = DemoCustomerRepository.get_session(serial_number)
    if session:
        DemoSessionRepository.update_status(session["id"], "pass_installed")

        # Schedule follow-up notification (5 min later)
        push_tokens = DemoDeviceRepository.get_push_tokens(serial_number)
        if push_tokens:
            asyncio.create_task(
                schedule_followup_notification(serial_number, push_tokens)
            )

    print(f"Demo device registered: {device_library_id[:20]}... for customer {serial_number[:8]}...")

    return Response(status_code=201)


@router.delete("/wallet/v1/devices/{device_library_id}/registrations/{pass_type_id}/{serial_number}")
def unregister_demo_device(
    device_library_id: str,
    pass_type_id: str,
    serial_number: str,
    authorization: str | None = Header(None),
):
    """Unregister demo device from push notifications."""
    auth_token = verify_auth_token(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization required")

    customer = DemoCustomerRepository.get_by_auth_token(serial_number, auth_token)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    DemoDeviceRepository.unregister(serial_number, device_library_id)

    print(f"Demo device unregistered: {device_library_id[:20]}...")

    return Response(status_code=200)


@router.get("/wallet/v1/devices/{device_library_id}/registrations/{pass_type_id}")
def get_demo_serial_numbers(
    device_library_id: str,
    pass_type_id: str,
    passesUpdatedSince: str | None = None,  # noqa: N803 - Apple Wallet API requirement
):
    """Get list of demo passes registered to this device that have been updated."""
    serial_numbers = DemoDeviceRepository.get_serial_numbers_for_device(device_library_id)

    if not serial_numbers:
        return Response(status_code=204)

    # For demo, we always return all passes (simpler than tracking updated_at)
    return {
        "serialNumbers": serial_numbers,
        "lastUpdated": str(int(time.time())),
    }


@router.get("/wallet/v1/passes/{pass_type_id}/{serial_number}")
def get_latest_demo_pass(
    pass_type_id: str,
    serial_number: str,
    authorization: str | None = Header(None),
):
    """Return latest version of demo pass."""
    auth_token = verify_auth_token(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization required")

    customer = DemoCustomerRepository.get_by_auth_token(serial_number, auth_token)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # Check if this is a follow-up notification (pass installed > 5 mins ago)
    followup_message = None
    created_at = customer.get("created_at")
    if created_at:
        if isinstance(created_at, str):
            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            created_dt = created_at
        # If pass was created more than 5 minutes ago, include promo message
        if (datetime.now(timezone.utc) - created_dt).total_seconds() > 300:
            followup_message = "See? We can reach your customers like this. Ready to create your own? Visit stampeo.app"

    generator = create_demo_pass_generator()
    pass_data = generator.generate_demo_pass(
        customer_id=customer["id"],
        stamps=customer["stamps"],
        auth_token=customer["auth_token"],
        followup_message=followup_message,
    )

    return Response(
        content=pass_data,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Last-Modified": formatdate(timeval=None, localtime=False, usegmt=True),
        }
    )


@router.post("/wallet/v1/log")
def receive_demo_logs(body: dict = Body(...)):
    """Receive error logs from Apple Wallet for demo passes."""
    logs = body.get("logs", [])
    for log in logs:
        print(f"Demo wallet log: {log}")
    return Response(status_code=200)
