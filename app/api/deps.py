from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session.
    Yields a database session and ensures proper cleanup.
    """
    async with AsyncSession(engine) as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """
    Check if database connection is healthy.
    Returns True if connection is successful, False otherwise.
    """
    try:
        async with AsyncSession(engine) as session:
            # Simple query to test connection
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        return True
    except Exception:
        return False
