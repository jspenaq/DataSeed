from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rate_limiter import RateLimiter
from app.core.redis import get_redis_client
from app.database import engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session.
    Yields a database session and ensures proper cleanup.
    """
    async with AsyncSession(engine) as session:
        yield session


async def rate_limiter_dependency(
    request: Request,
    response: Response,
    redis_client = Depends(get_redis_client)
) -> None:
    """
    FastAPI dependency for rate limiting using token-bucket algorithm.
    
    Rate limits are applied per API key (if provided) or per IP address.
    Default limits: 120 requests capacity, 2 tokens/second refill rate.
    
    Raises:
        HTTPException: 429 Too Many Requests if rate limit exceeded
    """
    # Get client identifier from API key header or fall back to IP
    api_key = request.headers.get("X-API-Key")
    if api_key:
        identifier = f"api_key:{api_key}"
    else:
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        identifier = f"ip:{client_ip}"
    
    # Initialize rate limiter with capacity=120, refill_rate=2 tokens/sec
    rate_limiter = RateLimiter(
        capacity=120,
        refill_rate=2.0,
        redis_client=redis_client
    )
    
    # Check if request is allowed
    is_allowed, remaining_tokens, reset_time = await rate_limiter.is_allowed(identifier)
    
    # Set rate limit headers
    response.headers["X-RateLimit-Limit"] = "120"
    response.headers["X-RateLimit-Remaining"] = str(remaining_tokens)
    response.headers["X-RateLimit-Reset"] = str(int(reset_time))
    
    if not is_allowed:
        # Calculate retry-after in seconds
        import time
        retry_after = max(1, int(reset_time - time.time()))
        
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Too many requests.",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": "120",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_time))
            }
        )
