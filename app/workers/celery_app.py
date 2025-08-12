from celery import Celery

from app.config import settings

# Create Celery app
celery_app = Celery(
    "DataSeed",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

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
        from app.core.redis import check_redis_connection

        return await check_redis_connection()
    except Exception:
        return False
