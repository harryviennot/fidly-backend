import logging
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from database import init_db
from app.api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown


def get_cors_origins() -> list[str]:
    """Get allowed CORS origins based on environment."""
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        return [
            "https://stampeo.app",
            "https://app.stampeo.app",
            "https://scanner.stampeo.app",
        ]

    # Development: allow all
    return ["*"]


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware that supports wildcard subdomains in production."""

    STAMPEO_PATTERN = re.compile(r"^https://([a-z0-9-]+\.)?stampeo\.app$")

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        env = os.getenv("ENVIRONMENT", "development")

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
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Credentials"] = "true"
            else:
                # Development: allow all origins
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"

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

    # Dynamic CORS middleware for subdomain support
    app.add_middleware(DynamicCORSMiddleware)

    # Include all routes
    app.include_router(api_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
