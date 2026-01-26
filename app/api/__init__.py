from fastapi import APIRouter

from .routes import customers, passes, stamps, wallet, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(passes.router, prefix="/passes", tags=["passes"])
api_router.include_router(stamps.router, prefix="/stamps", tags=["stamps"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
