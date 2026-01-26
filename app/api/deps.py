from functools import lru_cache

from app.services.pass_generator import PassGenerator, create_pass_generator_with_active_design
from app.services.apns import APNsClient, create_apns_client


async def get_pass_generator() -> PassGenerator:
    """Get a PassGenerator with the currently active design."""
    return await create_pass_generator_with_active_design()


@lru_cache
def get_apns_client() -> APNsClient:
    return create_apns_client()
