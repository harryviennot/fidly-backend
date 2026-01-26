from pydantic import BaseModel, EmailStr
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
