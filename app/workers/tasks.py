"""
Celery tasks for DataSeed ETL pipeline.

This module contains all Celery tasks for data ingestion from various sources.
Tasks are designed to be idempotent and include comprehensive error handling.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.extractors.base import ExtractorConfig
from app.core.extractors.hackernews import HackerNewsExtractor
from app.core.normalizers.content import get_normalizer
from app.core.services.ingestion import IngestionService
from app.database import engine
from app.models.source import Source
from app.schemas.items import ContentItemCreate


@shared_task(name="ingest.hackernews")
def ingest_hackernews_task() -> dict[str, Any]:
    """
    Celery task to ingest HackerNews data.

    This task orchestrates the complete HackerNews ETL pipeline:
    1. Fetches recent items from HackerNews API
    2. Normalizes and validates the data
    3. Performs batch upsert to database
    4. Tracks ingestion run statistics

    Returns:
        Dict with ingestion statistics: processed, new, updated counts
    """
    logger.info("Starting HackerNews ingestion task")

    try:
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're in a loop, create a task instead of using asyncio.run()
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _ingest_hn_async())
                result = future.result()
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            result = asyncio.run(_ingest_hn_async())

        logger.info("HackerNews ingestion task completed successfully", extra=result)
        return result
    except Exception as e:
        logger.error(f"HackerNews ingestion task failed: {e}", exc_info=True)
        return {"processed": 0, "new": 0, "updated": 0, "error": str(e)}


async def _ingest_hn_async() -> dict[str, Any]:
    """
    Async orchestration function for HackerNews ingestion.

    Returns:
        Dict with ingestion statistics
    """
    async with AsyncSession(engine) as session:
        try:
            # 1) Locate source
            source = await get_source_by_name(session, "hackernews")
            if not source:
                raise ValueError("HackerNews source not found in database")

            # 2) Determine since timestamp
            since = await get_last_since(session, source.id)
            if not since:
                since = datetime.now(UTC) - timedelta(hours=24)

            logger.info(f"Fetching HackerNews items since {since}")

            # 3) Start ingestion run
            run_id = await _start_run(session, source.id)

            try:
                # 4) Extract data from HackerNews
                # Refresh the source object to avoid lazy loading issues
                await session.refresh(source)

                extractor_config = ExtractorConfig(
                    base_url=source.base_url, rate_limit=source.rate_limit, config=source.config,
                )

                async with HackerNewsExtractor(extractor_config) as extractor:
                    raw_items = await extractor.fetch_recent(since=since, limit=100)

                logger.info(f"Extracted {len(raw_items)} raw items from HackerNews")

                # 5) Normalize data
                normalizer = get_normalizer("hackernews", source.id)
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

                # 6) Upsert to database
                ingestion_service = IngestionService(session)
                upsert_stats = await ingestion_service.batch_upsert_items(normalized_items, ingestion_run_id=run_id)

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
                    "HN ingestion completed successfully",
                    extra={
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
            logger.error(f"HackerNews ingestion failed: {e}", exc_info=True)
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
        stmt = select(Source).where(Source.name == name, Source.is_active == True)
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
    session: AsyncSession, run_id: int, items_processed: int, items_new: int, items_updated: int, errors: int,
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


def _normalize_hn(raw_item: dict[str, Any], source_id: int) -> ContentItemCreate:
    """
    Helper function to normalize a single HackerNews item.

    This function is kept for compatibility with the PRD specification,
    but the actual normalization is handled by the normalizer classes.

    Args:
        raw_item: Raw item data from HackerNews
        source_id: ID of the HackerNews source

    Returns:
        Normalized ContentItemCreate object
    """
    # This function is deprecated in favor of the normalizer classes
    # but kept for backward compatibility
    from app.core.extractors.base import RawItem

    # Convert dict to RawItem first
    raw_item_obj = RawItem(**raw_item)

    # Use the normalizer
    normalizer = get_normalizer("hackernews", source_id)
    return normalizer.normalize(raw_item_obj)
