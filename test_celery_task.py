#!/usr/bin/env python3
"""
Test script for the HackerNews Celery task.

This script tests the HackerNews ingestion task to ensure it works correctly
with the existing database and services.
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.workers.tasks import _ingest_hn_async, ingest_hackernews_task


async def test_async_function():
    """Test the async ingestion function directly."""
    print("Testing async HackerNews ingestion function...")

    try:
        result = await _ingest_hn_async()
        print("✅ Async function test passed!")
        print(f"Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Async function test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_celery_task():
    """Test the Celery task wrapper."""
    print("Testing Celery task wrapper...")

    try:
        result = ingest_hackernews_task()
        print("✅ Celery task test passed!")
        print(f"Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Celery task test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting HackerNews Celery task tests...\n")

    # Test 1: Async function
    async_success = await test_async_function()
    print()

    # Test 2: Celery task wrapper
    celery_success = test_celery_task()
    print()

    # Summary
    if async_success and celery_success:
        print("🎉 All tests passed! The HackerNews Celery task is working correctly.")
        return 0
    print("💥 Some tests failed. Please check the errors above.")
    return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
