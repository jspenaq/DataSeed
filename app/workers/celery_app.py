from celery import Celery, Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine


class DBSessionTask(Task):
    """
    Custom Celery Task base class that manages database session lifecycle.

    This class implements the Dependency Inversion Principle by providing
    a managed database session that is automatically created and cleaned up
    for each task execution.
    """

    _db_session = None

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """
        Clean up database session after task completion.

        This method is called after the task returns, regardless of success or failure.
        It ensures that the database session is properly closed to prevent connection leaks.
        """
        if self._db_session:
            # For async sessions, we need to run the close in an event loop
            import asyncio

            try:
                # Try to get the current event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, schedule the close as a task
                    loop.create_task(self._db_session.close())
                else:
                    # If no loop is running, run it directly
                    loop.run_until_complete(self._db_session.close())
            except RuntimeError:
                # No event loop available, create a new one
                asyncio.run(self._db_session.close())
            finally:
                self._db_session = None

    @property
    def db_session(self):
        """
        Get or create a database session for this task.

        Returns:
            AsyncSession: Database session instance
        """
        if self._db_session is None:
            self._db_session = AsyncSession(engine)
        return self._db_session


# Create Celery app
celery_app = Celery(
    "DataSeed",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Set the custom task class as the default
celery_app.Task = DBSessionTask

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
)

# Configure Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "schedule-all-sources": {
        "task": "schedule.all_sources",
        "schedule": 900.0,  # Every 15 minutes (900 seconds)
    },
}

# Import tasks to ensure they are registered with Celery
# This import must be after the celery_app is created to avoid circular imports
# pylint: disable=wrong-import-position
from app.workers import tasks  # noqa


async def check_celery_connection() -> bool:
    """
    Check if Celery/Redis connection is healthy.
    Returns True if connection is successful, False otherwise.
    """
    try:
        # Check if broker is available
        if not settings.CELERY_BROKER_URL:
            return False

        # We use the Redis client directly to check connection
        # since Celery doesn't provide a simple way to check connection health
        from app.core.health_checks import check_redis_connection

        return await check_redis_connection()
    except Exception:
        return False
