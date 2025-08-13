import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.rate_limiter import RateLimiter


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = MagicMock()
    
    # Mock pipeline - return a regular mock, not AsyncMock
    pipeline_mock = MagicMock()
    pipeline_mock.get = MagicMock()
    pipeline_mock.set = MagicMock()
    pipeline_mock.execute = AsyncMock()
    redis_mock.pipeline.return_value = pipeline_mock
    
    return redis_mock


@pytest.mark.asyncio
async def test_rate_limiter_first_request_allowed(mock_redis):
    """Test that the first request for a new identifier is allowed."""
    # Mock pipeline execution for first request (no existing data)
    pipeline_mock = mock_redis.pipeline.return_value
    pipeline_mock.execute.return_value = [None, None]  # No existing tokens or timestamp
    
    rate_limiter = RateLimiter(capacity=10, refill_rate=1.0, redis_client=mock_redis)
    
    is_allowed, remaining, reset_time = await rate_limiter.is_allowed("test_user")
    
    assert is_allowed is True
    assert remaining == 9  # Started with 10, consumed 1
    assert reset_time > time.time()
    
    # Verify Redis operations
    assert mock_redis.pipeline.call_count == 2  # One for get, one for set


@pytest.mark.asyncio
async def test_rate_limiter_subsequent_requests(mock_redis):
    """Test subsequent requests with existing tokens."""
    current_time = time.time()
    
    # Mock pipeline execution for existing data
    pipeline_mock = mock_redis.pipeline.return_value
    pipeline_mock.execute.side_effect = [
        [5.0, current_time - 1.0],  # 5 tokens, 1 second ago
        None  # Set operation result
    ]
    
    rate_limiter = RateLimiter(capacity=10, refill_rate=2.0, redis_client=mock_redis)
    
    is_allowed, remaining, reset_time = await rate_limiter.is_allowed("test_user")
    
    assert is_allowed is True
    # Should have 5 + (1 second * 2 tokens/sec) - 1 consumed = 6 tokens
    assert remaining == 6
    assert reset_time > current_time


@pytest.mark.asyncio
async def test_rate_limiter_no_tokens_denied(mock_redis):
    """Test that requests are denied when no tokens available."""
    current_time = time.time()
    
    # Mock pipeline execution for no tokens available
    pipeline_mock = mock_redis.pipeline.return_value
    pipeline_mock.execute.side_effect = [
        [0.5, current_time],  # 0.5 tokens, current time (not enough for 1 request)
        None  # Set operation result
    ]
    
    rate_limiter = RateLimiter(capacity=10, refill_rate=1.0, redis_client=mock_redis)
    
    is_allowed, remaining, reset_time = await rate_limiter.is_allowed("test_user")
    
    assert is_allowed is False
    assert remaining == 0
    assert reset_time > current_time


@pytest.mark.asyncio
async def test_rate_limiter_token_refill(mock_redis):
    """Test that tokens are properly refilled over time."""
    current_time = time.time()
    
    # Mock pipeline execution - 2 tokens, 5 seconds ago with 1 token/sec refill
    pipeline_mock = mock_redis.pipeline.return_value
    pipeline_mock.execute.side_effect = [
        [2.0, current_time - 5.0],  # 2 tokens, 5 seconds ago
        None  # Set operation result
    ]
    
    rate_limiter = RateLimiter(capacity=10, refill_rate=1.0, redis_client=mock_redis)
    
    is_allowed, remaining, reset_time = await rate_limiter.is_allowed("test_user")
    
    assert is_allowed is True
    # Should have min(10, 2 + 5) - 1 = 6 tokens remaining
    assert remaining == 6


@pytest.mark.asyncio
async def test_rate_limiter_capacity_cap(mock_redis):
    """Test that token count is capped at capacity."""
    current_time = time.time()
    
    # Mock pipeline execution - 8 tokens, 10 seconds ago with capacity 10
    pipeline_mock = mock_redis.pipeline.return_value
    pipeline_mock.execute.side_effect = [
        [8.0, current_time - 10.0],  # 8 tokens, 10 seconds ago
        None  # Set operation result
    ]
    
    rate_limiter = RateLimiter(capacity=10, refill_rate=1.0, redis_client=mock_redis)
    
    is_allowed, remaining, reset_time = await rate_limiter.is_allowed("test_user")
    
    assert is_allowed is True
    # Should be capped at capacity: min(10, 8 + 10) - 1 = 9 tokens remaining
    assert remaining == 9


@pytest.mark.asyncio
async def test_rate_limiter_different_identifiers(mock_redis):
    """Test that different identifiers have separate token buckets."""
    # Mock pipeline execution for first identifier
    pipeline_mock = mock_redis.pipeline.return_value
    pipeline_mock.execute.side_effect = [
        [None, None],  # First identifier - no existing data
        None,  # Set operation
        [None, None],  # Second identifier - no existing data  
        None   # Set operation
    ]
    
    rate_limiter = RateLimiter(capacity=5, refill_rate=1.0, redis_client=mock_redis)
    
    # Test first identifier
    is_allowed1, remaining1, _ = await rate_limiter.is_allowed("user1")
    assert is_allowed1 is True
    assert remaining1 == 4
    
    # Test second identifier (should have separate bucket)
    is_allowed2, remaining2, _ = await rate_limiter.is_allowed("user2")
    assert is_allowed2 is True
    assert remaining2 == 4