"""
Test configuration and fixtures for DataSeed tests.

Provides database fixtures, async session management, and test utilities.
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

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
    # Set a dummy Redis URL to avoid Redis connection issues in tests
    os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
    yield
    # Cleanup
    if "TESTING" in os.environ:
        del os.environ["TESTING"]


@pytest.fixture
def test_settings():
    """Get test settings."""
    return settings


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for testing."""
    mock_client = MagicMock()

    # Mock pipeline behavior - pipeline methods are synchronous
    mock_pipeline = MagicMock()
    mock_pipeline.get.return_value = mock_pipeline
    mock_pipeline.set.return_value = mock_pipeline
    mock_pipeline.execute = AsyncMock(return_value=[None, None])  # Default: no existing tokens
    mock_client.pipeline.return_value = mock_pipeline

    return mock_client


@pytest.fixture(autouse=True)
def mock_redis_dependency(mock_redis_client):
    """Mock the Redis dependency for all tests."""
    from app.core.redis import get_redis_client
    from app.main import app

    def override_get_redis_client():
        yield mock_redis_client

    app.dependency_overrides[get_redis_client] = override_get_redis_client
    yield
    # Clean up dependency override
    if get_redis_client in app.dependency_overrides:
        del app.dependency_overrides[get_redis_client]
