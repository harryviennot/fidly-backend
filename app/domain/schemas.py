from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# ============================================
# Business Schemas
# ============================================

class BusinessCreate(BaseModel):
    name: str
    url_slug: str = Field(..., pattern=r'^[a-z0-9-]+$', min_length=3, max_length=50)
    subscription_tier: str = Field(default="pay", pattern=r'^(pay|pro)$')
    settings: Optional[dict] = None
    logo_url: Optional[str] = None


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    subscription_tier: Optional[str] = Field(default=None, pattern=r'^(pay|pro)$')
    stripe_customer_id: Optional[str] = None
    settings: Optional[dict] = None
    logo_url: Optional[str] = None


class BusinessResponse(BaseModel):
    id: str
    name: str
    url_slug: str
    subscription_tier: str
    stripe_customer_id: Optional[str] = None
    settings: dict = {}
    logo_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================
# User Schemas
# ============================================

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    avatar_url: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================
# Membership Schemas
# ============================================

class MembershipCreate(BaseModel):
    user_id: str
    business_id: str
    role: str = Field(default="scanner", pattern=r'^(owner|admin|scanner)$')


class MembershipUpdate(BaseModel):
    role: str = Field(..., pattern=r'^(owner|admin|scanner)$')


class MembershipResponse(BaseModel):
    id: str
    user_id: str
    business_id: str
    role: str
    invited_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    scans_count: Optional[int] = 0
    user: Optional[UserResponse] = None
    business: Optional[BusinessResponse] = None


# ============================================
# Customer Schemas
# ============================================


class CustomerCreate(BaseModel):
    name: str
    email: EmailStr


class CustomerResponse(BaseModel):
    id: str
    name: str
    email: str
    stamps: int
    pass_url: Optional[str] = None  # Apple Wallet pass download URL
    google_wallet_url: Optional[str] = None  # Google Wallet save URL
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StampResponse(BaseModel):
    customer_id: str
    name: str
    stamps: int
    message: str


# Public customer registration (no auth required)
class CustomerPublicCreate(BaseModel):
    """Request body for public customer registration."""
    name: Optional[str] = None  # Required if business.settings.collect_name is true
    email: Optional[EmailStr] = None  # Required if business.settings.collect_email is true
    phone: Optional[str] = None  # Required if business.settings.collect_phone is true


class CustomerPublicResponse(BaseModel):
    """Response body for public customer registration."""
    status: str  # "created" | "exists_email_sent"
    customer_id: Optional[str] = None  # Only for "created"
    pass_url: Optional[str] = None  # Only for "created" - Apple Wallet
    google_wallet_url: Optional[str] = None  # Only for "created" - Google Wallet
    message: str  # User-friendly message


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

    # Icon configuration
    stamp_icon: str = "checkmark"
    reward_icon: str = "gift"
    icon_color: str = "rgb(255, 255, 255)"

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

    # Icon configuration
    stamp_icon: Optional[str] = None
    reward_icon: Optional[str] = None
    icon_color: Optional[str] = None

    # Pass fields
    secondary_fields: Optional[list[PassField]] = None
    auxiliary_fields: Optional[list[PassField]] = None
    back_fields: Optional[list[PassField]] = None


class CardDesignResponse(BaseModel):
    """Response body for a card design."""
    id: str
    name: str
    is_active: bool
    strip_status: str = "ready"  # 'ready' or 'regenerating'

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

    # Icon configuration
    stamp_icon: str = "checkmark"
    reward_icon: str = "gift"
    icon_color: str = "rgb(255, 255, 255)"

    # Asset URLs (populated by API)
    logo_url: Optional[str] = None
    custom_filled_stamp_url: Optional[str] = None
    custom_empty_stamp_url: Optional[str] = None
    strip_background_url: Optional[str] = None

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


# ============================================
# Onboarding Progress Schemas
# ============================================

class CardDesignProgress(BaseModel):
    """Card design state during onboarding."""
    background_color: str = "#1c1c1e"
    accent_color: str = "#f97316"
    icon_color: Optional[str] = None  # Stamp icon color (defaults to accent_color if not set)
    logo_url: Optional[str] = None
    stamp_icon: Optional[str] = None  # 'checkmark' | 'coffee' | 'star' | 'heart' | 'gift' | 'thumbsup'
    reward_icon: Optional[str] = None  # Final stamp (reward) icon: 'gift' | 'trophy' | 'star' | 'crown' | etc.


class OnboardingProgressCreate(BaseModel):
    """Request body for saving onboarding progress."""
    business_name: str
    url_slug: str
    owner_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    card_design: Optional[CardDesignProgress] = None
    current_step: int = Field(default=1, ge=1, le=6)
    completed_steps: List[int] = []


class OnboardingProgressResponse(BaseModel):
    """Response body for onboarding progress."""
    id: str
    user_id: str
    business_name: str
    url_slug: str
    owner_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    card_design: Optional[dict] = None
    current_step: int
    completed_steps: List[int]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================
# Invitation Schemas
# ============================================

class InvitationCreate(BaseModel):
    """Request body for creating an invitation."""
    email: EmailStr
    name: Optional[str] = None
    role: str = Field(default="scanner", pattern=r'^(admin|scanner)$')


class InvitationResponse(BaseModel):
    """Response body for an invitation (internal use)."""
    id: str
    business_id: str
    email: str
    name: Optional[str] = None
    role: str
    token: str
    status: str
    invited_by: str
    expires_at: datetime
    created_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    inviter: Optional[UserResponse] = None


class InvitationPublicResponse(BaseModel):
    """Public response for invitation acceptance page (no sensitive data)."""
    id: str
    email: str
    name: Optional[str] = None
    role: str
    status: str
    expires_at: datetime
    business_name: str
    inviter_name: str
    is_expired: bool
