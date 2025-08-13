"""
Test configuration and fixtures for DataSeed tests.

Provides database fixtures, async session management, and test utilities.
"""

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.models.base import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    # Use in-memory SQLite for tests
    test_database_url = "sqlite+aiosqlite:///:memory:"

    engine = create_async_engine(
        test_database_url,
        echo=False,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for each test with proper isolation."""
    # Create session directly
    session = AsyncSession(test_engine, expire_on_commit=False)

    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        # Clean up all data after each test for isolation
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    yield
    # Cleanup
    if "TESTING" in os.environ:
        del os.environ["TESTING"]


@pytest.fixture
def test_settings():
    """Get test settings."""
    return settings
