#!/usr/bin/env python3
"""
Demo script to showcase HTTP caching functionality.

This script demonstrates:
1. ETag generation based on request parameters and data state
2. Conditional requests with If-None-Match headers
3. 304 Not Modified responses when data hasn't changed
4. Cache headers in successful responses
"""

import asyncio
from datetime import UTC, datetime

from app.api.caching import (
    check_conditional_headers,
    generate_data_fingerprint,
    generate_etag,
    generate_request_fingerprint,
)


class MockRequest:
    """Mock FastAPI Request for demonstration."""

    def __init__(self, path: str, query_params: dict):
        self.url = MockURL(path)
        self.query_params = query_params
        self.headers = {}

    def set_header(self, name: str, value: str):
        self.headers[name] = value


class MockURL:
    """Mock URL object."""

    def __init__(self, path: str):
        self.path = path


class MockDB:
    """Mock database session for demonstration."""

    def __init__(self, item_count: int = 100, last_updated: datetime = None):
        self.item_count = item_count
        self.last_updated = last_updated or datetime.now(UTC)

    async def execute(self, query):
        """Mock query execution."""
        return MockResult(self.item_count, self.last_updated)


class MockResult:
    """Mock query result."""

    def __init__(self, count: int, max_updated_at: datetime):
        self.count = count
        self.max_updated_at = max_updated_at

    def one(self):
        return self


async def demo_caching():
    """Demonstrate HTTP caching functionality."""
    print("🚀 DataSeed HTTP Caching Demo")
    print("=" * 50)

    # 1. Request Fingerprint Generation
    print("\n1. Request Fingerprint Generation")
    print("-" * 30)

    request1 = MockRequest("/api/v1/items", {"source_name": "hackernews", "limit": "20"})
    request2 = MockRequest("/api/v1/items", {"source_name": "reddit", "limit": "20"})
    request3 = MockRequest("/api/v1/items", {"source_name": "hackernews", "limit": "20"})  # Same as request1

    fp1 = generate_request_fingerprint(request1)
    fp2 = generate_request_fingerprint(request2)
    fp3 = generate_request_fingerprint(request3)

    print(f"Request 1 (hackernews): {fp1}")
    print(f"Request 2 (reddit):     {fp2}")
    print(f"Request 3 (hackernews): {fp3}")
    print(f"Request 1 == Request 3: {fp1 == fp3}")
    print(f"Request 1 != Request 2: {fp1 != fp2}")

    # 2. Data Fingerprint Generation
    print("\n2. Data Fingerprint Generation")
    print("-" * 30)

    db1 = MockDB(item_count=100, last_updated=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC))
    db2 = MockDB(item_count=150, last_updated=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC))
    db3 = MockDB(item_count=100, last_updated=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC))  # Same as db1

    data_fp1, last_mod1 = await generate_data_fingerprint(db1)
    data_fp2, last_mod2 = await generate_data_fingerprint(db2)
    data_fp3, last_mod3 = await generate_data_fingerprint(db3)

    print(f"Data State 1 (100 items): {data_fp1}")
    print(f"Data State 2 (150 items): {data_fp2}")
    print(f"Data State 3 (100 items): {data_fp3}")
    print(f"Data State 1 == Data State 3: {data_fp1 == data_fp3}")
    print(f"Data State 1 != Data State 2: {data_fp1 != data_fp2}")

    # 3. ETag Generation
    print("\n3. ETag Generation")
    print("-" * 30)

    etag1 = generate_etag(fp1, data_fp1)
    etag2 = generate_etag(fp1, data_fp2)  # Same request, different data
    etag3 = generate_etag(fp2, data_fp1)  # Different request, same data
    etag4 = generate_etag(fp1, data_fp1)  # Same request, same data

    print(f"ETag 1 (req1 + data1): {etag1}")
    print(f"ETag 2 (req1 + data2): {etag2}")
    print(f"ETag 3 (req2 + data1): {etag3}")
    print(f"ETag 4 (req1 + data1): {etag4}")
    print(f"ETag 1 == ETag 4: {etag1 == etag4}")
    print(f"All ETags unique: {len({etag1, etag2, etag3}) == 3}")

    # 4. Conditional Request Handling
    print("\n4. Conditional Request Handling")
    print("-" * 30)

    # Mock request with If-None-Match header
    request_with_etag = MockRequest("/api/v1/items", {"source_name": "hackernews"})
    request_with_etag.headers = {"If-None-Match": etag1}

    # Check if cache is valid (should return True for matching ETag)
    cache_valid = await check_conditional_headers(request_with_etag, etag1, last_mod1)
    print(f"Client ETag matches server ETag: {cache_valid}")
    print("→ Server should return 304 Not Modified")

    # Check with different ETag (should return False)
    request_with_different_etag = MockRequest("/api/v1/items", {"source_name": "hackernews"})
    request_with_different_etag.headers = {"If-None-Match": etag2}

    cache_invalid = await check_conditional_headers(request_with_different_etag, etag1, last_mod1)
    print(f"Client ETag differs from server ETag: {not cache_invalid}")
    print("→ Server should return 200 OK with fresh data")

    # 5. Cache Headers Demo
    print("\n5. Cache Headers")
    print("-" * 30)

    print("Response headers for successful requests:")
    print(f"ETag: {etag1}")
    print(f"Last-Modified: {last_mod1.strftime('%a, %d %b %Y %H:%M:%S GMT')}")
    print("Cache-Control: public, max-age=30, stale-while-revalidate=60")
    print("Vary: Accept, X-API-Key")

    # 6. Performance Benefits
    print("\n6. Performance Benefits")
    print("-" * 30)

    print("✅ Reduced bandwidth: 304 responses have no body")
    print("✅ Faster responses: No database queries for unchanged data")
    print("✅ Lower server load: Conditional requests are lightweight")
    print("✅ Better UX: Instant responses for cached content")
    print("✅ CDN friendly: Standard HTTP caching headers")

    print("\n🎉 Caching implementation complete!")
    print("The API now supports efficient HTTP caching with ETags and conditional requests.")


if __name__ == "__main__":
    asyncio.run(demo_caching())
