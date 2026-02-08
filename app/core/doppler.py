"""
Doppler secrets loader for production deployment.

Fetches secrets from Doppler API and writes certificates to files.
Call this before app startup when DOPPLER_TOKEN is set.
"""

import os

import requests

DOPPLER_API_URL = "https://api.doppler.com/v3/configs/config/secrets/download"


def load_doppler_secrets() -> bool:
    """
    Load secrets from Doppler API and write certificates to files.

    Returns:
        True if secrets were loaded, False if DOPPLER_TOKEN not set.
    """
    token = os.getenv("DOPPLER_TOKEN")
    if not token:
        print("DOPPLER_TOKEN not set, using local env vars")
        return False

    # Fetch all secrets from Doppler
    response = requests.get(
        DOPPLER_API_URL,
        params={"format": "json"},
        auth=(token, ""),  # Service token as username, empty password
        timeout=30,
    )
    response.raise_for_status()
    secrets = response.json()

    # Set regular env vars
    env_vars = [
        "BASE_URL",
        "WEB_APP_URL",
        "SHOWCASE_URL",
        "APPLE_TEAM_ID",
        "APPLE_PASS_TYPE_ID",
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "GOOGLE_WALLET_ISSUER_ID",
    ]
    for key in env_vars:
        if key in secrets:
            os.environ[key] = secrets[key]

    # Write certificate files
    cert_dir = "/app/certs"
    os.makedirs(cert_dir, exist_ok=True)

    cert_mappings = {
        "SIGNER_CERT_PEM": "signerCert.pem",
        "SIGNER_KEY_PEM": "signerKey.pem",
        "WWDR_PEM": "wwdr.pem",
        "APNS_COMBINED_PEM": "combined.pem",
        "GOOGLE_WALLET_KEY_JSON": "google-wallet-key.json",
    }

    for secret_name, filename in cert_mappings.items():
        if secret_name in secrets:
            filepath = os.path.join(cert_dir, filename)
            with open(filepath, "w") as f:
                f.write(secrets[secret_name])
            os.chmod(filepath, 0o600)  # Secure permissions

    # Set certificate paths as env vars
    os.environ["CERT_PATH"] = "certs/signerCert.pem"
    os.environ["KEY_PATH"] = "certs/signerKey.pem"
    os.environ["WWDR_PATH"] = "certs/wwdr.pem"
    os.environ["APNS_CERT_PATH"] = "certs/combined.pem"
    os.environ["GOOGLE_WALLET_CREDENTIALS_PATH"] = "certs/google-wallet-key.json"
    os.environ["APNS_USE_SANDBOX"] = "false"

    print(f"Loaded {len(secrets)} secrets from Doppler")
    return True


if __name__ == "__main__":
    load_doppler_secrets()
