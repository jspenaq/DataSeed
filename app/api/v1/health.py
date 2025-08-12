from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_database_connection, get_db
from app.core.redis import check_redis_connection
from app.schemas.common import HealthCheckResult, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, status_code=200)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Comprehensive health check endpoint.

    Checks the health of all system components:
    - API (always healthy if this endpoint is responding)
    - Database connection
    - Redis/Celery connection

    Returns:
        HealthResponse: Health status of all components
    """
    # Check database connection
    db_healthy = await check_database_connection()
    db_result = HealthCheckResult(
        status="healthy" if db_healthy else "unhealthy",
        details={"connected": db_healthy},
        error=None if db_healthy else "Database connection failed",
    )

    # Check Redis/Celery connection
    redis_healthy = await check_redis_connection()
    redis_result = HealthCheckResult(
        status="healthy" if redis_healthy else "unhealthy",
        details={"connected": redis_healthy},
        error=None if redis_healthy else "Redis connection failed",
    )

    # Determine overall status
    checks: dict[str, HealthCheckResult] = {
        "api": HealthCheckResult(status="healthy"),
        "database": db_result,
        "redis": redis_result,
    }

    # If all checks are healthy, the system is healthy
    # If any check is unhealthy, the system is degraded or unhealthy
    all_healthy = all(check.status == "healthy" for check in checks.values())
    any_unhealthy = any(check.status == "unhealthy" for check in checks.values())

    status: Literal["healthy", "degraded", "unhealthy"]
    if all_healthy:
        status = "healthy"
    elif any_unhealthy and db_healthy:  # If DB is healthy but something else isn't, we're degraded
        status = "degraded"
    else:  # If DB is unhealthy, the whole system is unhealthy
        status = "unhealthy"
        # Return 503 Service Unavailable if the system is unhealthy
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is unhealthy",
        )

    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version="0.1.0",  # This could be pulled from a version file or environment variable
        checks=checks,
    )
