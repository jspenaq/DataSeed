"""
Celery tasks for DataSeed ETL pipeline.

This module contains all Celery tasks for data ingestion from various sources.
Tasks are designed to be idempotent and include comprehensive error handling.
The tasks follow the Dependency Inversion Principle by using factory functions
to create extractors and normalizers dynamically based on source names.
"""

import asyncio
import concurrent.futures
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.extractors.base import ExtractorConfig
from app.core.registry import get_extractor, get_normalizer
from app.core.services.ingestion import IngestionService
from app.models.source import Source
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="ingest.source")
def ingest_source_task(self, source_name: str) -> dict[str, Any]:
    """
    Generic Celery task to ingest data from any registered source.

    This task orchestrates the complete ETL pipeline for any data source:
    1. Fetches recent items from the source API using the appropriate extractor
    2. Normalizes and validates the data using the appropriate normalizer
    3. Performs batch upsert to database
    4. Tracks ingestion run statistics

    Args:
        source_name: Name of the source to ingest (e.g., "hackernews", "reddit")

    Returns:
        Dict with ingestion statistics: processed, new, updated counts
    """
    logger.info(f"Starting {source_name} ingestion task")

    try:
        # Check if an event loop is already running in the current thread
        asyncio.get_running_loop()

        # If so, it's safer to run the new event loop in a separate thread
        # to avoid conflicts.
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # We submit a lambda that calls asyncio.run(), ensuring a clean event loop.
            future = executor.submit(lambda: asyncio.run(_ingest_source_async(self, source_name)))
            result = future.result()

    except RuntimeError:
        # If no event loop is running, we can safely start one.
        result = asyncio.run(_ingest_source_async(self, source_name))

    except Exception as e:
        logger.error(f"{source_name} ingestion task failed: {e}", exc_info=True)
        return {"processed": 0, "new": 0, "updated": 0, "error": str(e)}

    log_extra = {
        "source_name": source_name,
        "processed": result["processed"],
        "new": result["new"],
        "updated": result["updated"],
        "errors": result["errors"],
    }
    logger.info(f"{source_name} ingestion task completed successfully", extra=log_extra)
    return result


async def _ingest_source_async(task_instance, source_name: str) -> dict[str, Any]:
    """
    Generic async orchestration function for source ingestion.

    Args:
        task_instance: The Celery task instance with db_session property
        source_name: Name of the source to ingest

    Returns:
        Dict with ingestion statistics
    """
    session = task_instance.db_session
    try:
        # 1) Locate source
        source = await get_source_by_name(session, source_name)
        if not source:
            raise ValueError(f"{source_name} source not found in database")

        # 2) Determine since timestamp
        since = await get_last_since(session, source.id)
        if not since:
            since = datetime.now(UTC) - timedelta(hours=24)

        logger.info(f"Fetching {source_name} items since {since}")

        # 3) Start ingestion run
        run_id = await _start_run(session, source.id)

        try:
            # 4) Extract data using factory-created extractor
            # Refresh the source object to avoid lazy loading issues
            await session.refresh(source)

            extractor_config = ExtractorConfig(
                base_url=source.base_url,
                rate_limit=source.rate_limit,
                config=source.config,
            )

            # Use factory function to get the appropriate extractor
            async with get_extractor(source_name, extractor_config) as extractor:
                raw_items = await extractor.fetch_recent(since=since, limit=100)

            logger.info(f"Extracted {len(raw_items)} raw items from {source_name}")

            # 5) Normalize data using factory-created normalizer
            normalizer = get_normalizer(source_name, source.id)
            normalized_items = []
            normalization_errors = 0

            for raw_item in raw_items:
                try:
                    normalized_item = normalizer.normalize(raw_item)
                    normalized_items.append(normalized_item)
                except Exception as e:
                    logger.warning(f"Failed to normalize item {raw_item.external_id}: {e}")
                    normalization_errors += 1

            logger.info(f"Normalized {len(normalized_items)} items ({normalization_errors} errors)")

            # 6) Upsert to database using service instantiated within task
            ingestion_service = IngestionService(session)
            upsert_stats = await ingestion_service.batch_upsert_items(normalized_items)

            # 7) Complete ingestion run
            await _finish_run(
                session,
                run_id,
                items_processed=len(normalized_items),
                items_new=upsert_stats["new"],
                items_updated=upsert_stats["updated"],
                errors=normalization_errors + upsert_stats["failed"],
            )

            result = {
                "processed": len(normalized_items),
                "new": upsert_stats["new"],
                "updated": upsert_stats["updated"],
                "errors": normalization_errors + upsert_stats["failed"],
            }

            logger.info(
                f"{source_name} ingestion completed successfully",
                extra={
                    "source": source_name,
                    "processed": result["processed"],
                    "new": result["new"],
                    "updated": result["updated"],
                    "errors": result["errors"],
                },
            )

            return result

        except Exception as e:
            # Mark run as failed
            await _fail_run(session, run_id, str(e))
            raise

    except Exception as e:
        logger.error(f"{source_name} ingestion failed: {e}", exc_info=True)
        raise


# Backward compatibility task for HackerNews
@shared_task(name="ingest.hackernews")
def ingest_hackernews_task() -> dict[str, Any]:
    """
    Backward compatibility wrapper for HackerNews ingestion.

    This task is kept for backward compatibility but delegates to the generic
    ingest_source_task with "hackernews" as the source name.

    Returns:
        Dict with ingestion statistics: processed, new, updated counts
    """
    # Use the celery_app.task decorator to call the bound task properly
    return ingest_source_task.apply(args=["hackernews"]).get()


@celery_app.task(bind=True, name="schedule.all_sources")
def schedule_all_sources_task(self) -> dict[str, Any]:
    """
    Periodic task that queries all active sources and schedules ingestion tasks.
    
    This task runs every 15 minutes and dynamically dispatches ingest_source_task
    for each active source in the database. This provides a flexible scheduling
    mechanism that doesn't require hardcoded source names.
    
    Returns:
        Dict with scheduling statistics: sources_found, tasks_scheduled
    """
    logger.info("Starting scheduled ingestion for all active sources")
    
    try:
        # Check if an event loop is already running in the current thread
        asyncio.get_running_loop()
        
        # If so, run in a separate thread to avoid conflicts
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(_schedule_all_sources_async(self)))
            result = future.result()
            
    except RuntimeError:
        # If no event loop is running, we can safely start one
        result = asyncio.run(_schedule_all_sources_async(self))
        
    except Exception as e:
        logger.error(f"Failed to schedule source ingestion tasks: {e}", exc_info=True)
        return {"sources_found": 0, "tasks_scheduled": 0, "error": str(e)}
    
    logger.info(
        f"Scheduled ingestion completed: {result['tasks_scheduled']} tasks for {result['sources_found']} sources"
    )
    return result


async def _schedule_all_sources_async(task_instance) -> dict[str, Any]:
    """
    Async function to query active sources and schedule ingestion tasks.
    
    Args:
        task_instance: The Celery task instance with db_session property
        
    Returns:
        Dict with scheduling statistics
    """
    session = task_instance.db_session
    
    try:
        # Query all active sources
        stmt = select(Source).where(Source.is_active.is_(True))
        result = await session.execute(stmt)
        active_sources = result.scalars().all()
        
        logger.info(f"Found {len(active_sources)} active sources")
        
        tasks_scheduled = 0
        
        # Schedule ingestion task for each active source
        for source in active_sources:
            try:
                # Use apply_async to schedule the task without waiting for completion
                ingest_source_task.apply_async(args=[source.name])
                tasks_scheduled += 1
                logger.info(f"Scheduled ingestion task for source: {source.name}")
                
            except Exception as e:
                logger.error(f"Failed to schedule ingestion for source {source.name}: {e}")
        
        return {
            "sources_found": len(active_sources),
            "tasks_scheduled": tasks_scheduled,
        }
        
    except Exception as e:
        logger.error(f"Failed to query active sources: {e}", exc_info=True)
        raise


async def get_source_by_name(session: AsyncSession, name: str) -> Source | None:
    """
    Get a source by name from the database.

    Args:
        session: Database session
        name: Source name to look up

    Returns:
        Source instance or None if not found
    """
    try:
        stmt = select(Source).where(Source.name == name, Source.is_active.is_(True))
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Failed to get source by name '{name}': {e}")
        return None


async def get_last_since(session: AsyncSession, source_id: int) -> datetime | None:
    """
    Get the timestamp of the last successful ingestion for a source.

    Args:
        session: Database session
        source_id: ID of the source

    Returns:
        Datetime of last successful ingestion or None
    """
    try:
        from app.models.ingestion import IngestionRun

        stmt = (
            select(IngestionRun.completed_at)
            .where(IngestionRun.source_id == source_id, IngestionRun.status == "completed")
            .order_by(IngestionRun.completed_at.desc())
            .limit(1)
        )

        result = await session.execute(stmt)
        last_completed = result.scalar_one_or_none()

        if last_completed:
            # Add a small buffer to avoid missing items at the boundary
            return last_completed - timedelta(minutes=5)

        return None

    except Exception as e:
        logger.error(f"Failed to get last ingestion time for source {source_id}: {e}")
        return None


async def _start_run(session: AsyncSession, source_id: int) -> int:
    """
    Start a new ingestion run and return its ID.

    Args:
        session: Database session
        source_id: ID of the source being ingested

    Returns:
        ID of the created ingestion run

    Raises:
        Exception: If run creation fails
    """
    try:
        ingestion_service = IngestionService(session)
        run = await ingestion_service.create_ingestion_run(source_id)

        # Update status to running
        await ingestion_service.update_ingestion_run(run.id, status="running")

        logger.info(f"Started ingestion run {run.id} for source {source_id}")
        return run.id

    except Exception as e:
        logger.error(f"Failed to start ingestion run for source {source_id}: {e}")
        raise


async def _finish_run(
    session: AsyncSession,
    run_id: int,
    items_processed: int,
    items_new: int,
    items_updated: int,
    errors: int,
) -> None:
    """
    Mark an ingestion run as completed with final statistics.

    Args:
        session: Database session
        run_id: ID of the ingestion run
        items_processed: Total items processed
        items_new: Number of new items created
        items_updated: Number of items updated
        errors: Number of errors encountered
    """
    try:
        ingestion_service = IngestionService(session)

        status = "completed" if errors == 0 else "failed"

        await ingestion_service.update_ingestion_run(
            run_id=run_id,
            status=status,
            items_processed=items_processed,
            items_new=items_new,
            items_updated=items_updated,
            items_failed=errors,
            errors_count=errors,
            completed_at=datetime.now(UTC),
        )

        logger.info(f"Finished ingestion run {run_id} with status {status}")

    except Exception as e:
        logger.error(f"Failed to finish ingestion run {run_id}: {e}")
        # Don't raise here to avoid masking the original error


async def _fail_run(session: AsyncSession, run_id: int, error_message: str) -> None:
    """
    Mark an ingestion run as failed with error details.

    Args:
        session: Database session
        run_id: ID of the ingestion run
        error_message: Error message to record
    """
    try:
        ingestion_service = IngestionService(session)

        await ingestion_service.update_ingestion_run(
            run_id=run_id,
            status="failed",
            error_notes=error_message[:1000],  # Truncate to fit database field
            completed_at=datetime.now(UTC),
        )

        logger.info(f"Marked ingestion run {run_id} as failed")

    except Exception as e:
        logger.error(f"Failed to mark ingestion run {run_id} as failed: {e}")
