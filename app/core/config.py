import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwt_secret: str = ""  # JWT secret for HS256 token verification

    # Apple Developer
    apple_team_id: str = ""
    apple_pass_type_id: str = ""

    # Certificates
    cert_path: str = "certs/signerCert.pem"
    key_path: str = "certs/signerKey.pem"
    wwdr_path: str = "certs/wwdr.pem"
    cert_password: str | None = None

    # Server
    base_url: str = "http://localhost:8000"

    # Business
    business_name: str = "Coffee Shop"

    # Strip image customization (visual stamps on pass)
    strip_background_color: str = "rgb(139, 90, 43)"  # Coffee brown
    strip_stamp_filled_color: str = "rgb(255, 215, 0)"  # Gold
    strip_stamp_empty_color: str = "rgb(80, 50, 20)"  # Dark brown
    strip_stamp_border_color: str = "rgb(255, 255, 255)"  # White
    strip_custom_filled_icon: str | None = None  # e.g., "coffee_stamp.png"
    strip_custom_empty_icon: str | None = None  # e.g., "coffee_empty.png"

    # APNs
    apns_use_sandbox: bool = False
    apns_cert_path: str = "certs/combined.pem"

    # ngrok
    ngrok_api_url: str | None = None

    # Email (Resend)
    resend_api_key: str = ""
    web_app_url: str = "http://localhost:3000"

    # Showcase (customer-facing landing pages)
    showcase_url: str = "http://localhost:3001"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
