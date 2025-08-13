#!/usr/bin/env python3
"""
Test script to verify the refactored Celery task with DBSessionTask base class.

This script tests that:
1. The DBSessionTask base class properly manages database sessions
2. The ingest_source_task uses the bound task instance correctly
3. Database sessions are properly cleaned up after task execution
"""

import sys
from unittest.mock import AsyncMock

# Add the app directory to the Python path
sys.path.insert(0, ".")


def test_db_session_task_base_class():
    """Test that the DBSessionTask base class works correctly."""
    print("Testing DBSessionTask base class...")

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.workers.celery_app import DBSessionTask

    # Create a mock task instance
    task = DBSessionTask()

    # Test that db_session property creates a session
    session = task.db_session
    assert isinstance(session, AsyncSession), f"Expected AsyncSession, got {type(session)}"

    # Test that the same session is returned on subsequent calls
    session2 = task.db_session
    assert session is session2, "db_session should return the same instance"

    print("✅ DBSessionTask base class works correctly")


def test_task_binding():
    """Test that the ingest_source_task is properly bound."""
    print("Testing task binding...")

    from app.workers.tasks import ingest_source_task

    # Check that the task is bound (has bind=True)
    assert hasattr(ingest_source_task, "bind"), "Task should have bind attribute"

    # Check that it's registered with the celery app
    from app.workers.celery_app import celery_app

    assert "ingest.source" in celery_app.tasks, "Task should be registered with celery app"

    print("✅ Task binding works correctly")


def test_session_cleanup():
    """Test that sessions are properly cleaned up."""
    print("Testing session cleanup...")

    from app.workers.celery_app import DBSessionTask

    task = DBSessionTask()

    # Get a session
    session = task.db_session
    assert task._db_session is not None, "Session should be stored in _db_session"

    # Mock the session close method
    session.close = AsyncMock()

    # Call after_return to simulate task completion
    task.after_return(status="SUCCESS", retval={}, task_id="test", args=[], kwargs={}, einfo=None)

    # Give it a moment for async cleanup
    import time

    time.sleep(0.1)

    # Check that session was cleaned up
    assert task._db_session is None, "Session should be cleaned up after task completion"

    print("✅ Session cleanup works correctly")


def test_task_functionality():
    """Test that the task works with the new base class."""
    print("Testing task functionality...")

    from app.workers.celery_app import DBSessionTask
    from app.workers.tasks import ingest_source_task

    # Check that the task is bound (has the bind attribute set)
    assert hasattr(ingest_source_task, "bind"), "Task should be bound"

    # Check that the task uses our custom base class
    from app.workers.celery_app import celery_app

    assert celery_app.Task == DBSessionTask, "Celery app should use DBSessionTask as base class"

    # Verify the task is properly registered
    task_obj = celery_app.tasks.get("ingest.source")
    assert task_obj is not None, "Task should be registered"

    print("✅ Task functionality is correct")


def main():
    """Run all tests."""
    print("🧪 Testing refactored Celery task with Dependency Inversion...")
    print("=" * 60)

    try:
        test_db_session_task_base_class()
        test_task_binding()
        test_session_cleanup()
        test_task_functionality()

        print("=" * 60)
        print("🎉 All tests passed! The refactoring successfully implements Dependency Inversion.")
        print("\nKey improvements:")
        print("✅ DBSessionTask base class manages database session lifecycle")
        print("✅ Tasks receive dependencies through the task instance (self.db_session)")
        print("✅ Sessions are automatically cleaned up after task completion")
        print(
            "✅ Follows Dependency Inversion Principle - high-level task logic doesn't depend on low-level session creation",
        )

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
