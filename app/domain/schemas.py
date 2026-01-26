from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class CustomerCreate(BaseModel):
    name: str
    email: EmailStr


class CustomerResponse(BaseModel):
    id: str
    name: str
    email: str
    stamps: int
    pass_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StampResponse(BaseModel):
    customer_id: str
    name: str
    stamps: int
    message: str


class DeviceRegistration(BaseModel):
    pushToken: str


class ErrorResponse(BaseModel):
    detail: str


# Card Design Schemas

class PassField(BaseModel):
    """A field on the pass (secondary, auxiliary, or back field)."""
    key: str
    label: str
    value: str


class StampConfig(BaseModel):
    """Stamp styling configuration."""
    total_stamps: int = Field(default=10, ge=1, le=20)
    filled_color: str = "rgb(255, 215, 0)"
    empty_color: str = "rgb(80, 50, 20)"
    border_color: str = "rgb(255, 255, 255)"


class CardDesignCreate(BaseModel):
    """Request body for creating a card design."""
    name: str
    organization_name: str
    description: str
    logo_text: Optional[str] = None

    # Colors
    foreground_color: str = "rgb(255, 255, 255)"
    background_color: str = "rgb(139, 90, 43)"
    label_color: str = "rgb(255, 255, 255)"

    # Stamp config
    total_stamps: int = Field(default=10, ge=1, le=20)
    stamp_filled_color: str = "rgb(255, 215, 0)"
    stamp_empty_color: str = "rgb(80, 50, 20)"
    stamp_border_color: str = "rgb(255, 255, 255)"

    # Pass fields
    secondary_fields: list[PassField] = []
    auxiliary_fields: list[PassField] = []
    back_fields: list[PassField] = []


class CardDesignUpdate(BaseModel):
    """Request body for updating a card design. All fields optional."""
    name: Optional[str] = None
    organization_name: Optional[str] = None
    description: Optional[str] = None
    logo_text: Optional[str] = None

    # Colors
    foreground_color: Optional[str] = None
    background_color: Optional[str] = None
    label_color: Optional[str] = None

    # Stamp config
    total_stamps: Optional[int] = Field(default=None, ge=1, le=20)
    stamp_filled_color: Optional[str] = None
    stamp_empty_color: Optional[str] = None
    stamp_border_color: Optional[str] = None

    # Pass fields
    secondary_fields: Optional[list[PassField]] = None
    auxiliary_fields: Optional[list[PassField]] = None
    back_fields: Optional[list[PassField]] = None


class CardDesignResponse(BaseModel):
    """Response body for a card design."""
    id: str
    name: str
    is_active: bool

    organization_name: str
    description: str
    logo_text: Optional[str] = None

    # Colors
    foreground_color: str
    background_color: str
    label_color: str

    # Stamp config
    total_stamps: int
    stamp_filled_color: str
    stamp_empty_color: str
    stamp_border_color: str

    # Asset URLs (populated by API)
    logo_url: Optional[str] = None
    custom_filled_stamp_url: Optional[str] = None
    custom_empty_stamp_url: Optional[str] = None

    # Pass fields
    secondary_fields: list[PassField] = []
    auxiliary_fields: list[PassField] = []
    back_fields: list[PassField] = []

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UploadResponse(BaseModel):
    """Response body for a file upload."""
    id: str
    asset_type: str
    url: str
    filename: str
