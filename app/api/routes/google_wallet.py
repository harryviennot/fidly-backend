"""
Google Wallet callback endpoint.

Handles callbacks from Google Wallet when:
- A pass is saved to wallet
- A pass is deleted from wallet
"""

import json
import logging

from fastapi import APIRouter, Body, Response, HTTPException

from app.repositories.callback_nonce import CallbackNonceRepository
from app.services.wallets.google import create_google_wallet_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/callback")
def google_wallet_callback(
    body: dict = Body(...),
):
    """
    Handle Google Wallet callback.

    Google sends POST requests to this endpoint when users interact
    with their passes (save, delete, etc.).

    The callback payload is signed and includes a signedMessage field
    that contains JSON with:
    - eventType: 'save' | 'del' | etc.
    - classId: The class ID
    - objectId: The object ID (contains customer ID)
    - nonce: Unique identifier for deduplication

    Returns:
        200 OK if callback was processed successfully
    """
    # Parse the signedMessage - Google sends the actual data as a JSON string
    # inside the signedMessage field (part of their signing protocol)
    callback_data = body
    if "signedMessage" in body:
        try:
            callback_data = json.loads(body["signedMessage"])
        except json.JSONDecodeError as e:
            logger.error(f"[Google Wallet Callback] Failed to parse signedMessage: {e}")

    # Extract nonce for deduplication
    nonce = callback_data.get("nonce")

    if nonce:
        # Check if we've already processed this callback
        if CallbackNonceRepository.exists(nonce):
            return Response(status_code=200)

        # Mark nonce as processed
        CallbackNonceRepository.mark_processed(nonce)

    # Process the callback
    try:
        google_service = create_google_wallet_service()
        google_service.handle_callback(callback_data)
        return {"status": "ok"}

    except Exception as e:
        # Log error but still return 200 to prevent retries
        logger.error(f"[Google Wallet Callback] Error processing callback: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.get("/callback")
def google_wallet_callback_verify():
    """
    Verify callback URL for Google Wallet setup.

    Google may GET this endpoint to verify it's reachable.
    """
    return {"status": "ok", "service": "google-wallet-callback"}
