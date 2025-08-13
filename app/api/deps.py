from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session.
    Yields a database session and ensures proper cleanup.
    """
    async with AsyncSession(engine) as session:
        yield session
