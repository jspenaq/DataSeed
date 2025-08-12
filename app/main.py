from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine

app = FastAPI(title="DataSeed")


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/v1/health/db")
async def health_db() -> dict[str, str]:
    """Test database connection health."""
    try:
        async with AsyncSession(engine) as session:
            # Simple query to test connection
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "database": "disconnected", "error": str(e)},
        )
