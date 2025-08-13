#!/usr/bin/env python3
"""
Test script to verify GitHub ETag conditional requests implementation.
"""

import asyncio
import os
from datetime import datetime, timedelta

from app.core.extractors.github import GitHubExtractor
from app.core.extractors.base import ExtractorConfig
from app.core.redis import RedisClient


async def test_github_etag_caching():
    """Test GitHub ETag caching functionality."""
    print("Testing GitHub ETag conditional requests...")

    # Configuration for GitHub extractor
    config = ExtractorConfig(
        base_url="https://api.github.com",
        rate_limit=60,
        config={
            "token": os.getenv("GITHUB_TOKEN"),  # Optional, but recommended
            "search_endpoint": "/search/repositories",
            "mode": "search",
        },
    )

    # Create extractor instance
    extractor = GitHubExtractor(config, source_id=1)

    try:
        print("\n1. First request (should fetch fresh data)...")
        since = datetime.now() - timedelta(hours=1)
        items1 = await extractor.fetch_recent(since=since, limit=5)
        print(f"   Fetched {len(items1)} items")

        print("\n2. Second request immediately (should use cached ETag)...")
        items2 = await extractor.fetch_recent(since=since, limit=5)
        print(f"   Fetched {len(items2)} items")

        if len(items2) == 0:
            print("   ✅ ETag caching working - received 304 Not Modified")
        else:
            print("   ⚠️  ETag caching may not be working - received new data")

        print("\n3. Testing cache key generation...")
        test_url = "https://api.github.com/search/repositories?q=test"
        cache_key = extractor._get_cache_key(test_url)
        print(f"   Cache key for '{test_url}': {cache_key}")

        # Verify cache key format
        if cache_key.startswith("github:etag:") and len(cache_key) == 52:  # 12 + 40 (SHA1 hex)
            print("   ✅ Cache key format is correct")
        else:
            print("   ❌ Cache key format is incorrect")

        print("\n4. Testing Redis connection...")
        redis_client = await extractor._get_redis_client()
        await redis_client.ping()
        print("   ✅ Redis connection successful")

        print("\n5. Testing releases mode with ETag...")
        releases_config = ExtractorConfig(
            base_url="https://api.github.com",
            rate_limit=60,
            config={
                "token": os.getenv("GITHUB_TOKEN"),
                "mode": "releases",
                "repositories": ["microsoft/vscode", "python/cpython"],
            },
        )

        releases_extractor = GitHubExtractor(releases_config, source_id=1)

        print("   First releases request...")
        releases1 = await releases_extractor.fetch_recent(limit=3)
        print(f"   Fetched {len(releases1)} releases")

        print("   Second releases request (should use ETags)...")
        releases2 = await releases_extractor.fetch_recent(limit=3)
        print(f"   Fetched {len(releases2)} releases")

        if len(releases2) == 0:
            print("   ✅ ETag caching working for releases")
        else:
            print("   ⚠️  ETag caching may not be working for releases")

        await releases_extractor.close()

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await extractor.close()
        await RedisClient.close()

    print("\n✅ ETag testing completed!")


if __name__ == "__main__":
    asyncio.run(test_github_etag_caching())
