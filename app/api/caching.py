import hashlib
import json
from datetime import UTC, datetime

import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.redis import get_redis_client
from app.models.items import ContentItem


class CacheInfo:
    """Container for cache-related information."""

    def __init__(self, etag: str, last_modified: datetime, should_return_304: bool = False) -> None:
        self.etag = etag
        self.last_modified = last_modified
        self.should_return_304 = should_return_304


def generate_request_fingerprint(request: Request) -> str:
    """
    Generate a fingerprint for the request based on path and query parameters.

    Args:
        request: FastAPI Request object

    Returns:
        SHA256 hash of the request fingerprint
    """
    # Create a consistent representation of the request
    fingerprint_data = {
        "path": str(request.url.path),
        "query_params": dict(request.query_params),
    }

    # Sort the dictionary to ensure consistent ordering
    fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)

    # Generate SHA256 hash
    return hashlib.sha256(fingerprint_json.encode()).hexdigest()[:16]


async def generate_data_fingerprint(
    db: AsyncSession,
    source_name: str | None = None,
    q: str | None = None,
    window_start: datetime | None = None,
) -> tuple[str, datetime]:
    """
    Generate a fingerprint for the current state of the data.

    Args:
        db: Database session
        source_name: Optional source filter
        q: Optional search query
        window_start: Optional time window filter

    Returns:
        Tuple of (data_fingerprint, latest_updated_at)
    """
    from app.models.source import Source

    # Build query to get count and latest updated_at
    query = select(
        func.count(ContentItem.id).label("count"),
        func.max(ContentItem.updated_at).label("max_updated_at"),
    ).select_from(ContentItem)

    # Apply filters similar to the main queries
    if source_name:
        query = query.join(Source).where(Source.name == source_name)

    if q:
        from sqlalchemy import or_

        query = query.where(or_(ContentItem.title.ilike(f"%{q}%"), ContentItem.content.ilike(f"%{q}%")))

    if window_start:
        query = query.where(ContentItem.published_at >= window_start)

    result = await db.execute(query)
    row = result.one()

    count = row.count or 0
    max_updated_at = row.max_updated_at or datetime.now(UTC)

    # Create data fingerprint from count and timestamp
    data_info = f"{count}:{max_updated_at.isoformat()}"
    data_fingerprint = hashlib.sha256(data_info.encode()).hexdigest()[:16]

    return data_fingerprint, max_updated_at


def generate_etag(request_fingerprint: str, data_fingerprint: str) -> str:
    """
    Generate a weak ETag from request and data fingerprints.

    Args:
        request_fingerprint: Hash of request parameters
        data_fingerprint: Hash of data state

    Returns:
        Weak ETag string
    """
    combined = f"{request_fingerprint}:{data_fingerprint}"
    etag_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
    return f'W/"{etag_hash}"'


async def check_conditional_headers(request: Request, etag: str, last_modified: datetime) -> bool:
    """
    Check If-None-Match and If-Modified-Since headers.

    Args:
        request: FastAPI Request object
        etag: Current ETag value
        last_modified: Current last modified timestamp

    Returns:
        True if client cache is still valid (should return 304)
    """
    # Check If-None-Match header (ETag-based)
    if_none_match = request.headers.get("If-None-Match")
    if if_none_match and (if_none_match == "*" or etag in if_none_match):
        return True

    # Check If-Modified-Since header (timestamp-based)
    if_modified_since = request.headers.get("If-Modified-Since")
    if if_modified_since:
        try:
            # Parse HTTP date format
            from email.utils import parsedate_to_datetime

            client_timestamp = parsedate_to_datetime(if_modified_since)

            # Compare timestamps (ignore microseconds for HTTP compatibility)
            if last_modified.replace(microsecond=0) <= client_timestamp.replace(microsecond=0):
                return True
        except (ValueError, TypeError):
            # Invalid date format, ignore
            pass

    return False


async def cache_dependency(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> CacheInfo:
    """
    FastAPI dependency for HTTP caching with ETag and Last-Modified headers.

    This dependency:
    1. Generates ETags based on request parameters and data state
    2. Checks conditional request headers (If-None-Match, If-Modified-Since)
    3. Returns 304 Not Modified if client cache is valid
    4. Sets appropriate response headers for successful responses

    Args:
        request: FastAPI Request object
        response: FastAPI Response object
        db: Database session dependency
        redis_client: Redis client dependency

    Returns:
        CacheInfo object with ETag and caching information

    Raises:
        HTTPException: 304 Not Modified if client cache is valid
    """
    # Generate request fingerprint
    request_fingerprint = generate_request_fingerprint(request)

    # Extract common query parameters for data fingerprint
    source_name = request.query_params.get("source_name")
    q = request.query_params.get("q")

    # Handle window parameter for stats/trending endpoints
    window_start = None
    window = request.query_params.get("window")
    if window and request.url.path.endswith(("/stats", "/trending")):
        try:
            # timedelta is already imported at the top

            from app.api.v1.items import _parse_window

            window_delta = _parse_window(window)
            window_start = datetime.now(UTC) - window_delta
        except (ValueError, ImportError):
            pass

    # Generate data fingerprint
    data_fingerprint, last_modified = await generate_data_fingerprint(db, source_name, q, window_start)

    # Generate ETag
    etag = generate_etag(request_fingerprint, data_fingerprint)

    # Check conditional headers
    should_return_304 = await check_conditional_headers(request, etag, last_modified)

    if should_return_304:
        # Set headers and return 304 Not Modified
        response.headers["ETag"] = etag
        response.headers["Last-Modified"] = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
        response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
        response.headers["Vary"] = "Accept, X-API-Key"

        raise HTTPException(
            status_code=304,
            detail="Not Modified",
            headers={
                "ETag": etag,
                "Last-Modified": last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "Cache-Control": "public, max-age=30, stale-while-revalidate=60",
                "Vary": "Accept, X-API-Key",
            },
        )

    # Return cache info for successful responses
    return CacheInfo(etag=etag, last_modified=last_modified)


def set_cache_headers(response: Response, cache_info: CacheInfo) -> None:
    """
    Set cache-related response headers.

    Args:
        response: FastAPI Response object
        cache_info: CacheInfo object with ETag and timestamp
    """
    response.headers["ETag"] = cache_info.etag
    response.headers["Last-Modified"] = cache_info.last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    response.headers["Vary"] = "Accept, X-API-Key"
