"""API routes for offline scanner sync."""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends

from database.connection import get_db
from app.services.programs import ProgramService
from app.core.permissions import require_any_access, BusinessAccessContext

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{business_id}")
async def sync_offline_queue(
    body: dict,
    ctx: BusinessAccessContext = Depends(require_any_access),
):
    """
    Process a batch of offline scanner operations.

    Uses client_id for idempotency - duplicate client_ids are skipped.
    Items older than 24 hours are rejected.
    """
    items = body.get("items", [])
    if not items:
        return {"results": []}

    db = get_db()
    program_service = ProgramService()
    results = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    for item in items:
        client_id = item.get("client_id")
        if not client_id:
            results.append({"client_id": client_id, "status": "failed", "reason": "Missing client_id"})
            continue

        # Check age
        offline_at_str = item.get("created_offline_at")
        if offline_at_str:
            try:
                offline_at = datetime.fromisoformat(offline_at_str.replace("Z", "+00:00"))
                if offline_at < cutoff:
                    results.append({"client_id": client_id, "status": "failed", "reason": "Item too old (>24h)"})
                    continue
            except (ValueError, TypeError):
                pass

        # Check idempotency
        existing = db.table("offline_queue").select("id, status").eq("client_id", client_id).limit(1).execute()
        if existing and existing.data:
            results.append({"client_id": client_id, "status": "already_synced"})
            continue

        # Insert into queue
        try:
            db.table("offline_queue").insert({
                "client_id": client_id,
                "scanner_user_id": ctx.user["id"],
                "business_id": ctx.business_id,
                "customer_id": item.get("customer_id"),
                "program_id": item.get("program_id"),
                "action": item.get("action", "stamp"),
                "payload": item.get("payload", {}),
                "created_offline_at": offline_at_str or datetime.now(timezone.utc).isoformat(),
                "status": "processing",
            }).execute()
        except Exception as e:
            results.append({"client_id": client_id, "status": "failed", "reason": str(e)})
            continue

        # Process the action
        try:
            action = item.get("action", "stamp")
            customer_id = item.get("customer_id")

            if action == "stamp":
                result = await program_service.add_progress(
                    customer_id=customer_id,
                    business_id=ctx.business_id,
                    program_id=item.get("program_id"),
                    employee_id=ctx.user["id"],
                    source="scanner",
                )
                db.table("offline_queue").update({
                    "status": "synced",
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                }).eq("client_id", client_id).execute()

                results.append({
                    "client_id": client_id,
                    "status": "synced",
                    "transaction_id": result.transaction_id,
                })
            else:
                results.append({"client_id": client_id, "status": "failed", "reason": f"Unsupported action: {action}"})

        except Exception as e:
            logger.error(f"[Sync] Failed to process item {client_id}: {e}", exc_info=True)
            db.table("offline_queue").update({
                "status": "failed",
                "error_message": str(e),
            }).eq("client_id", client_id).execute()
            results.append({"client_id": client_id, "status": "failed", "reason": str(e)})

    return {"results": results}
