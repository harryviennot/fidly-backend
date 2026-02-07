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

    # Demo pass (optional - falls back to apple_pass_type_id if not set)
    demo_pass_type_id: str = ""
    demo_cert_path: str = "certs/demo/signer_cert.pem"
    demo_key_path: str = "certs/demo/signer_key.pem"
    demo_wwdr_path: str = "certs/wwdr.pem"
    demo_cert_password: str | None = None
    demo_apns_cert_path: str = "certs/demo/apns_combined.pem"

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

    # Google Wallet
    google_wallet_issuer_id: str = ""
    google_wallet_credentials_path: str = "certs/google-wallet-key.json"

    # Tunnel URL file (cloudflared writes public URL here)
    tunnel_url_file: str = "/tunnel/url"

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


def get_tunnel_url() -> str | None:
    """
    Get the public tunnel URL from cloudflared.

    The cloudflared container writes the URL to a file that's
    mounted into the backend container.

    Returns:
        The tunnel URL (e.g., "https://xxx.trycloudflare.com") or None if not available
    """
    try:
        with open(settings.tunnel_url_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def get_callback_url() -> str:
    """
    Get the Google Wallet callback URL.

    Uses the cloudflared tunnel URL if available, otherwise falls back to base_url.
    """
    tunnel_url = get_tunnel_url()
    base = tunnel_url if tunnel_url else settings.base_url
    return f"{base}/google-wallet/callback"


def get_public_base_url() -> str:
    """
    Get the public base URL for the API.

    Uses the cloudflared tunnel URL if available, otherwise falls back to base_url.
    """
    tunnel_url = get_tunnel_url()
    return tunnel_url if tunnel_url else settings.base_url
