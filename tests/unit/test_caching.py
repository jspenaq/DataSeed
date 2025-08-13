import hashlib
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.caching import (
    CacheInfo,
    cache_dependency,
    check_conditional_headers,
    generate_data_fingerprint,
    generate_etag,
    generate_request_fingerprint,
    set_cache_headers
)


def test_generate_request_fingerprint():
    """Test request fingerprint generation."""
    # Mock request
    request = MagicMock()
    request.url.path = "/api/v1/items"
    request.query_params = {"source_name": "hackernews", "limit": "20"}
    
    fingerprint = generate_request_fingerprint(request)
    
    # Should be a 16-character hex string
    assert len(fingerprint) == 16
    assert all(c in "0123456789abcdef" for c in fingerprint)
    
    # Same request should produce same fingerprint
    fingerprint2 = generate_request_fingerprint(request)
    assert fingerprint == fingerprint2
    
    # Different request should produce different fingerprint
    request.query_params = {"source_name": "reddit", "limit": "20"}
    fingerprint3 = generate_request_fingerprint(request)
    assert fingerprint != fingerprint3


@pytest.mark.asyncio
async def test_generate_data_fingerprint():
    """Test data fingerprint generation."""
    # Mock database session and result
    db = AsyncMock(spec=AsyncSession)
    
    # Mock query result
    mock_row = MagicMock()
    mock_row.count = 100
    mock_row.max_updated_at = datetime(2024, 1, 1, 12, 0, 0)
    
    mock_result = MagicMock()
    mock_result.one.return_value = mock_row
    
    db.execute.return_value = mock_result
    
    fingerprint, last_modified = await generate_data_fingerprint(db)
    
    # Should return fingerprint and timestamp
    assert len(fingerprint) == 16
    assert isinstance(last_modified, datetime)
    assert last_modified == datetime(2024, 1, 1, 12, 0, 0)
    
    # Database should have been queried
    db.execute.assert_called_once()


def test_generate_etag():
    """Test ETag generation."""
    request_fp = "abc123"
    data_fp = "def456"
    
    etag = generate_etag(request_fp, data_fp)
    
    # Should be a weak ETag
    assert etag.startswith('W/"')
    assert etag.endswith('"')
    assert len(etag) == 20  # W/" + 16 chars + "
    
    # Same inputs should produce same ETag
    etag2 = generate_etag(request_fp, data_fp)
    assert etag == etag2
    
    # Different inputs should produce different ETag
    etag3 = generate_etag("different", data_fp)
    assert etag != etag3


@pytest.mark.asyncio
async def test_check_conditional_headers_if_none_match():
    """Test If-None-Match header checking."""
    request = MagicMock()
    etag = 'W/"abc123"'
    last_modified = datetime.now(timezone.utc)
    
    # Test matching ETag
    request.headers.get.side_effect = lambda header: {
        "If-None-Match": 'W/"abc123"',
        "If-Modified-Since": None
    }.get(header)
    
    result = await check_conditional_headers(request, etag, last_modified)
    assert result is True
    
    # Test non-matching ETag
    request.headers.get.side_effect = lambda header: {
        "If-None-Match": 'W/"different"',
        "If-Modified-Since": None
    }.get(header)
    
    result = await check_conditional_headers(request, etag, last_modified)
    assert result is False
    
    # Test wildcard
    request.headers.get.side_effect = lambda header: {
        "If-None-Match": "*",
        "If-Modified-Since": None
    }.get(header)
    
    result = await check_conditional_headers(request, etag, last_modified)
    assert result is True


@pytest.mark.asyncio
async def test_check_conditional_headers_if_modified_since():
    """Test If-Modified-Since header checking."""
    
    request = MagicMock()
    etag = 'W/"abc123"'
    # Use timezone-aware datetime to match parsedate_to_datetime behavior
    last_modified = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    # Test older client timestamp (should return True - not modified)
    request.headers.get.side_effect = lambda header: {
        "If-None-Match": None,
        "If-Modified-Since": "Mon, 01 Jan 2024 13:00:00 GMT"  # 1 hour later
    }.get(header)
    
    result = await check_conditional_headers(request, etag, last_modified)
    assert result is True
    
    # Test newer client timestamp (should return False - modified)
    request.headers.get.side_effect = lambda header: {
        "If-None-Match": None,
        "If-Modified-Since": "Mon, 01 Jan 2024 11:00:00 GMT"  # 1 hour earlier
    }.get(header)
    
    result = await check_conditional_headers(request, etag, last_modified)
    assert result is False


def test_set_cache_headers():
    """Test setting cache headers on response."""
    response = MagicMock(spec=Response)
    response.headers = {}
    
    cache_info = CacheInfo(
        etag='W/"abc123"',
        last_modified=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    )
    
    set_cache_headers(response, cache_info)
    
    # Check all headers are set
    assert response.headers["ETag"] == 'W/"abc123"'
    assert response.headers["Last-Modified"] == "Mon, 01 Jan 2024 12:00:00 GMT"
    assert response.headers["Cache-Control"] == "public, max-age=30, stale-while-revalidate=60"
    assert response.headers["Vary"] == "Accept, X-API-Key"


@pytest.mark.asyncio
async def test_cache_dependency_304_response():
    """Test cache dependency returning 304 Not Modified."""
    # Mock request
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/items"
    request.query_params = {}
    request.headers.get.side_effect = lambda header: {
        "If-None-Match": 'W/"abc123"'
    }.get(header)
    
    # Mock response
    response = MagicMock(spec=Response)
    response.headers = {}
    
    # Mock database session
    db = AsyncMock(spec=AsyncSession)
    mock_row = MagicMock()
    mock_row.count = 100
    mock_row.max_updated_at = datetime(2024, 1, 1, 12, 0, 0)
    mock_result = MagicMock()
    mock_result.one.return_value = mock_row
    db.execute.return_value = mock_result
    
    # Mock Redis client
    redis_client = AsyncMock()
    
    # Mock the fingerprint generation to return predictable values
    with patch('app.api.caching.generate_request_fingerprint', return_value="request123"), \
         patch('app.api.caching.generate_data_fingerprint', return_value=("data456", datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))), \
         patch('app.api.caching.generate_etag', return_value='W/"abc123"'):
        
        # Should raise HTTPException with 304 status
        with pytest.raises(HTTPException) as exc_info:
            await cache_dependency(request, response, db, redis_client)
        
        assert exc_info.value.status_code == 304
        assert exc_info.value.detail == "Not Modified"
        assert exc_info.value.headers is not None
        assert "ETag" in exc_info.value.headers
        assert "Last-Modified" in exc_info.value.headers


@pytest.mark.asyncio
async def test_cache_dependency_200_response():
    """Test cache dependency returning cache info for 200 response."""
    # Mock request
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/items"
    request.query_params = {}
    request.headers.get.return_value = None  # No conditional headers
    
    # Mock response
    response = MagicMock(spec=Response)
    response.headers = {}
    
    # Mock database session
    db = AsyncMock(spec=AsyncSession)
    mock_row = MagicMock()
    mock_row.count = 100
    mock_row.max_updated_at = datetime(2024, 1, 1, 12, 0, 0)
    mock_result = MagicMock()
    mock_result.one.return_value = mock_row
    db.execute.return_value = mock_result
    
    # Mock Redis client
    redis_client = AsyncMock()
    
    # Mock the fingerprint generation to return predictable values
    with patch('app.api.caching.generate_request_fingerprint', return_value="request123"), \
         patch('app.api.caching.generate_data_fingerprint', return_value=("data456", datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))), \
         patch('app.api.caching.generate_etag', return_value='W/"abc123"'):
        
        cache_info = await cache_dependency(request, response, db, redis_client)
        
        assert isinstance(cache_info, CacheInfo)
        assert cache_info.etag == 'W/"abc123"'
        assert cache_info.last_modified == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert cache_info.should_return_304 is False