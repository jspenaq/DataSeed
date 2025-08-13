from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import core module to trigger registry auto-discovery
import app.core  # noqa: F401
from app.api.v1 import health, items
from app.config import settings

app = FastAPI(
    title="DataSeed",
    description="A developer-friendly data pipeline for public data sources",
    version="0.1.0",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix=settings.API_V1_STR, tags=["health"])
app.include_router(items.router, prefix=f"{settings.API_V1_STR}/items", tags=["items"])
