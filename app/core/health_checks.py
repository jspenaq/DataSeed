from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import RedisClient


class DatabaseHealthChecker(Protocol):
    """Protocol for database health checking."""

    async def check(self, db: AsyncSession) -> tuple[str, bool]:
        """Returns (component_name, is_healthy)"""
        ...


class CacheHealthChecker(Protocol):
    """Protocol for cache health checking."""

    async def check(self) -> tuple[str, bool]:
        """Returns (component_name, is_healthy)"""
        ...


class PostgreSQLHealthChecker:
    """Concrete implementation for PostgreSQL database health checking."""

    async def check(self, db: AsyncSession) -> tuple[str, bool]:
        """
        Check if PostgreSQL database connection is healthy.
        Returns ("database", is_healthy) tuple.
        """
        try:
            # Simple query to test connection
            result = await db.execute(text("SELECT 1"))
            result.scalar()
            return ("database", True)
        except Exception:
            return ("database", False)


class RedisHealthChecker:
    """Concrete implementation for Redis cache health checking."""

    async def check(self) -> tuple[str, bool]:
        """
        Check if Redis connection is healthy.
        Returns ("redis", is_healthy) tuple.
        """
        try:
            client = await RedisClient.get_redis()
            await client.ping()
            return ("redis", True)
        except Exception:
            return ("redis", False)


# Legacy function wrappers for backward compatibility
async def check_database_connection(db: AsyncSession) -> bool:
    """
    Legacy function for database health checking.
    Returns True if connection is successful, False otherwise.
    """
    checker = PostgreSQLHealthChecker()
    _, is_healthy = await checker.check(db)
    return is_healthy


async def check_redis_connection() -> bool:
    """
    Legacy function for Redis health checking.
    Returns True if connection is successful, False otherwise.
    """
    checker = RedisHealthChecker()
    _, is_healthy = await checker.check()
    return is_healthy
