from fastapi import APIRouter, HTTPException

from app.domain.schemas import BusinessCreate, BusinessUpdate, BusinessResponse
from app.repositories.business import BusinessRepository

router = APIRouter()


@router.post("", response_model=BusinessResponse)
def create_business(data: BusinessCreate):
    """Create a new business."""
    existing = BusinessRepository.get_by_slug(data.url_slug)
    if existing:
        raise HTTPException(status_code=400, detail="URL slug already taken")

    business = BusinessRepository.create(
        name=data.name,
        url_slug=data.url_slug,
        subscription_tier=data.subscription_tier,
        settings=data.settings,
    )
    if not business:
        raise HTTPException(status_code=500, detail="Failed to create business")
    return BusinessResponse(**business)


@router.get("", response_model=list[BusinessResponse])
def list_businesses():
    """Get all businesses."""
    businesses = BusinessRepository.get_all()
    return [BusinessResponse(**b) for b in businesses]


@router.get("/{business_id}", response_model=BusinessResponse)
def get_business(business_id: str):
    """Get a business by ID."""
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return BusinessResponse(**business)


@router.get("/slug/{url_slug}", response_model=BusinessResponse)
def get_business_by_slug(url_slug: str):
    """Get a business by URL slug."""
    business = BusinessRepository.get_by_slug(url_slug)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return BusinessResponse(**business)


@router.put("/{business_id}", response_model=BusinessResponse)
def update_business(business_id: str, data: BusinessUpdate):
    """Update a business."""
    existing = BusinessRepository.get_by_id(business_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Business not found")

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return BusinessResponse(**existing)

    business = BusinessRepository.update(business_id, **update_data)
    if not business:
        raise HTTPException(status_code=500, detail="Failed to update business")
    return BusinessResponse(**business)


@router.delete("/{business_id}")
def delete_business(business_id: str):
    """Delete a business."""
    existing = BusinessRepository.get_by_id(business_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Business not found")

    deleted = BusinessRepository.delete(business_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete business")
    return {"message": "Business deleted successfully"}
