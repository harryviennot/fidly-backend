from fastapi import APIRouter, Depends, Query

from app.domain.schemas import ActivityStatsResponse, TransactionListResponse, TransactionResponse
from app.repositories.transaction import TransactionRepository
from app.core.permissions import require_any_access, BusinessAccessContext
from database.connection import get_db

router = APIRouter()


def _enrich_rows(rows: list[dict]) -> None:
    """Batch-fetch employee names and customer info, then attach to rows."""
    db = get_db()

    # Employee names
    employee_ids = list({r["employee_id"] for r in rows if r.get("employee_id")})
    name_map: dict[str, str] = {}
    if employee_ids:
        result = db.table("users").select("id, name").in_("id", employee_ids).execute()
        name_map = {u["id"]: u["name"] for u in (result.data or [])}

    # Customer info
    customer_ids = list({r["customer_id"] for r in rows if r.get("customer_id")})
    customer_map: dict[str, dict] = {}
    if customer_ids:
        result = db.table("customers").select("id, name, email").in_("id", customer_ids).execute()
        customer_map = {c["id"]: c for c in (result.data or [])}

    for r in rows:
        r["employee_name"] = name_map.get(r.get("employee_id"))

        # Inject customer attributes into metadata for display
        cust = customer_map.get(r.get("customer_id"), {})
        meta = dict(r.get("metadata") or {})
        meta["customer_name"] = cust.get("name")
        meta["customer_email"] = cust.get("email")
        r["metadata"] = meta


@router.get("/{business_id}/stats", response_model=ActivityStatsResponse)
def get_activity_stats(
    ctx: BusinessAccessContext = Depends(require_any_access),
):
    """Get aggregate activity stats for the dashboard."""
    data = TransactionRepository.get_activity_stats(ctx.business_id)
    return ActivityStatsResponse(**data)


@router.get("/{business_id}", response_model=TransactionListResponse)
def list_business_transactions(
    customer_id: str | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: BusinessAccessContext = Depends(require_any_access),
):
    """List transactions for a business with optional filters."""
    rows, total = TransactionRepository.list_by_business(
        business_id=ctx.business_id,
        customer_id=customer_id,
        type_filter=type,
        limit=limit,
        offset=offset,
    )
    _enrich_rows(rows)
    return TransactionListResponse(
        transactions=[TransactionResponse(**r) for r in rows],
        total_count=total,
        has_more=(offset + limit) < total,
    )


@router.get("/{business_id}/{customer_id}", response_model=TransactionListResponse)
def list_customer_transactions(
    customer_id: str,
    type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: BusinessAccessContext = Depends(require_any_access),
):
    """List transaction history for a specific customer."""
    rows, total = TransactionRepository.list_by_business(
        business_id=ctx.business_id,
        customer_id=customer_id,
        type_filter=type,
        limit=limit,
        offset=offset,
    )
    _enrich_rows(rows)
    return TransactionListResponse(
        transactions=[TransactionResponse(**r) for r in rows],
        total_count=total,
        has_more=(offset + limit) < total,
    )
