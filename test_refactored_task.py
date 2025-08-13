#!/usr/bin/env python3
"""
Test script to verify the refactored Celery task works correctly.

This script tests the new generic ingest_source_task with the HackerNews source
to ensure the refactoring maintains functionality while improving flexibility.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.workers.tasks import ingest_hackernews_task, ingest_source_task


def test_generic_task():
    """Test the new generic ingest_source_task."""
    print("Testing generic ingest_source_task with 'hackernews'...")

    try:
        result = ingest_source_task("hackernews")
        print(f"✅ Generic task completed successfully: {result}")
        return True
    except Exception as e:
        print(f"❌ Generic task failed: {e}")
        return False


def test_backward_compatibility():
    """Test that the old HackerNews-specific task still works."""
    print("Testing backward compatibility with ingest_hackernews_task...")

    try:
        result = ingest_hackernews_task()
        print(f"✅ Backward compatibility task completed successfully: {result}")
        return True
    except Exception as e:
        print(f"❌ Backward compatibility task failed: {e}")
        return False


def test_invalid_source():
    """Test error handling with an invalid source name."""
    print("Testing error handling with invalid source 'nonexistent'...")

    try:
        result = ingest_source_task("nonexistent")
        if "error" in result:
            print(f"✅ Error handling works correctly: {result['error']}")
            return True
        print(f"❌ Expected error but got success: {result}")
        return False
    except Exception as e:
        print(f"✅ Exception handling works correctly: {e}")
        return True


def main():
    """Run all tests."""
    print("🧪 Testing Refactored Celery Task Implementation")
    print("=" * 50)

    tests = [
        ("Generic Task", test_generic_task),
        ("Backward Compatibility", test_backward_compatibility),
        ("Error Handling", test_invalid_source),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} Test:")
        success = test_func()
        results.append((test_name, success))
        print()

    print("=" * 50)
    print("📊 Test Results Summary:")

    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if success:
            passed += 1

    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("🎉 All tests passed! Refactoring successful.")
        return 0
    print("⚠️  Some tests failed. Please review the implementation.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
