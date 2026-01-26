from functools import lru_cache

from app.services.pass_generator import PassGenerator, create_pass_generator
from app.services.apns import APNsClient, create_apns_client


@lru_cache
def get_pass_generator() -> PassGenerator:
    return create_pass_generator()


@lru_cache
def get_apns_client() -> APNsClient:
    return create_apns_client()
