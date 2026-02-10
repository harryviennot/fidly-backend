from fastapi import APIRouter, Depends, Query

from app.domain.schemas import TransactionListResponse, TransactionResponse
from app.repositories.transaction import TransactionRepository
from app.core.permissions import require_any_access, BusinessAccessContext

router = APIRouter()


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
    return TransactionListResponse(
        transactions=[TransactionResponse(**r) for r in rows],
        total_count=total,
        has_more=(offset + limit) < total,
    )
