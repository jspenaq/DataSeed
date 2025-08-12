from collections.abc import AsyncGenerator

import redis.asyncio as redis

from app.config import settings


class RedisClient:
    _instance: redis.Redis | None = None

    @classmethod
    async def get_redis(cls) -> redis.Redis:
        """
        Get or create a Redis client instance.
        Uses a singleton pattern to avoid creating multiple connections.
        """
        if cls._instance is None:
            if not settings.CELERY_BROKER_URL:
                raise ValueError("CELERY_BROKER_URL is not configured")

            # Extract Redis URL from Celery broker URL
            # Assuming format: redis://host:port/db
            redis_url = settings.CELERY_BROKER_URL
            cls._instance = redis.from_url(redis_url, decode_responses=True)

        return cls._instance

    @classmethod
    async def close(cls) -> None:
        """Close the Redis connection if it exists."""
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None


async def get_redis_client() -> AsyncGenerator[redis.Redis, None]:
    """
    FastAPI dependency for Redis client.
    Yields a Redis client and ensures proper cleanup.
    """
    try:
        client = await RedisClient.get_redis()
        yield client
    finally:
        # We don't close the connection here to reuse it
        # Connection will be closed when the application shuts down
        pass


async def check_redis_connection() -> bool:
    """
    Check if Redis connection is healthy.
    Returns True if connection is successful, False otherwise.
    """
    try:
        client = await RedisClient.get_redis()
        await client.ping()
        return True
    except Exception:
        return False
