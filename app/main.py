import logging
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from database import init_db
from app.api import api_router
from app.core.rate_limit import limiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Suppress noisy library logs (only show warnings/errors)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("supabase").setLevel(logging.WARNING)
logging.getLogger("postgrest").setLevel(logging.WARNING)
logging.getLogger("gotrue").setLevel(logging.WARNING)
logging.getLogger("storage3").setLevel(logging.WARNING)
logging.getLogger("realtime").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown


logger = logging.getLogger(__name__)


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware that supports wildcard subdomains in production."""

    STAMPEO_PATTERN = re.compile(r"^https://([a-z0-9-]+\.)?stampeo\.app$")

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        env = os.getenv("ENVIRONMENT", "development")

        logger.info(f"CORS check - Origin: {origin}, Env: {env}, Method: {request.method}, Path: {request.url.path}")

        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response(status_code=200)
        else:
            response = await call_next(request)

        # Set CORS headers
        if origin:
            if env == "production":
                # Allow stampeo.app and any subdomain
                if self.STAMPEO_PATTERN.match(origin):
                    logger.info(f"CORS allowed for origin: {origin}")
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                else:
                    logger.warning(f"CORS rejected - Origin '{origin}' does not match pattern")
            else:
                # Development: allow all origins
                logger.info(f"CORS allowed (dev mode) for origin: {origin}")
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            logger.info("No origin header present in request")

        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"

        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="Loyalty Card POC",
        description="Apple Wallet Loyalty Card API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Dynamic CORS middleware for subdomain support
    app.add_middleware(DynamicCORSMiddleware)

    # Include all routes
    app.include_router(api_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
