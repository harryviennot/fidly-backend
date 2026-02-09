from functools import lru_cache

from app.services.pass_generator import PassGenerator, create_pass_generator
from app.services.apns import APNsClient, create_apns_client


def get_demo_pass_generator() -> PassGenerator:
    """Get a PassGenerator for demo passes (shared certs)."""
    return create_pass_generator()


@lru_cache
def get_demo_apns_client() -> APNsClient:
    """Get an APNsClient for demo passes (shared certs)."""
    return create_apns_client()
