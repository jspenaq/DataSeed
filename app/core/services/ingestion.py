"""
Ingestion service for handling batch upserts and tracking ingestion runs.

This module provides the core persistence layer for DataSeed's ETL pipeline,
including idempotent batch operations and comprehensive run tracking.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion import IngestionRun
from app.models.items import ContentItem
from app.schemas.items import ContentItemCreate


class IngestionService:
    """Service for handling data ingestion operations with proper tracking."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session

    async def batch_upsert_items(
        self,
        items: list[ContentItemCreate],
    ) -> dict[str, int]:
        """
        Perform batch upsert of content items with conflict resolution.

        Uses database-specific ON CONFLICT DO UPDATE to handle duplicates based on
        the unique constraint (source_id, external_id). Supports PostgreSQL and SQLite.

        Args:
            items: List of ContentItemCreate objects to upsert

        Returns:
            Dict with counts: {'new': int, 'updated': int, 'failed': int}

        Raises:
            SQLAlchemyError: If database operation fails
            NotImplementedError: If database dialect is not supported
        """
        if not items:
            logger.info("No items to upsert")
            return {"new": 0, "updated": 0, "failed": 0}

        logger.info(f"Starting batch upsert of {len(items)} items")

        try:
            # Convert Pydantic models to dict for bulk operations
            items_data = []
            for item in items:
                item_dict = item.model_dump()
                item_dict["created_at"] = datetime.now(UTC)
                item_dict["updated_at"] = datetime.now(UTC)
                items_data.append(item_dict)

            # Detect database dialect
            dialect = self.db.bind.dialect.name

            # Build the upsert statement based on dialect
            if dialect == "postgresql":
                stmt = pg_insert(ContentItem).values(items_data)

                # Define what to update on conflict
                update_dict = {
                    "title": stmt.excluded.title,
                    "content": stmt.excluded.content,
                    "url": stmt.excluded.url,
                    "score": stmt.excluded.score,
                    "published_at": stmt.excluded.published_at,
                    "updated_at": stmt.excluded.updated_at,
                }

                # Create the ON CONFLICT DO UPDATE statement
                upsert_stmt = stmt.on_conflict_do_update(constraint="uq_source_external", set_=update_dict)

            elif dialect == "sqlite":
                stmt = sqlite_insert(ContentItem).values(items_data)

                # Define what to update on conflict
                update_dict = {
                    "title": stmt.excluded.title,
                    "content": stmt.excluded.content,
                    "url": stmt.excluded.url,
                    "score": stmt.excluded.score,
                    "published_at": stmt.excluded.published_at,
                    "updated_at": stmt.excluded.updated_at,
                }

                # Create the ON CONFLICT DO UPDATE statement for SQLite
                upsert_stmt = stmt.on_conflict_do_update(index_elements=["source_id", "external_id"], set_=update_dict)

            else:
                raise NotImplementedError(f"Batch upsert not supported for dialect: {dialect}")

            # Pre-count existing items before executing the upsert
            pairs = [(item["source_id"], item["external_id"]) for item in items_data]
            existing_count = 0
            if pairs:
                conditions = [
                    and_(
                        ContentItem.source_id == source_id,
                        ContentItem.external_id == external_id,
                    )
                    for source_id, external_id in pairs
                ]
                pre_count_stmt = select(func.count()).select_from(ContentItem).where(or_(*conditions))
                existing_count = (await self.db.execute(pre_count_stmt)).scalar() or 0

            # Execute the upsert and get results
            result = await self.db.execute(upsert_stmt)
            await self.db.commit()

            # Calculate stats correctly
            affected = result.rowcount or 0
            updated = min(existing_count, affected)
            new = max(0, affected - updated)  # Use max to prevent negative numbers

            stats = {
                "new": new,
                "updated": updated,
                "failed": 0,  # No failures if we reach here
            }

            logger.info(
                f"Batch upsert completed: {stats['new']} new, {stats['updated']} updated, {stats['failed']} failed",
            )

            return stats

        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Batch upsert failed: {str(e)}")
            # Return all as failed
            return {"new": 0, "updated": 0, "failed": len(items)}

    async def create_ingestion_run(self, source_id: int, started_at: datetime | None = None) -> IngestionRun:
        """
        Create a new ingestion run record.

        Args:
            source_id: ID of the source being ingested
            started_at: When the run started (defaults to now)

        Returns:
            Created IngestionRun instance

        Raises:
            SQLAlchemyError: If database operation fails
        """
        if started_at is None:
            started_at = datetime.now(UTC)

        logger.info(f"Creating ingestion run for source_id={source_id}")

        try:
            ingestion_run = IngestionRun(source_id=source_id, started_at=started_at, status="started")

            self.db.add(ingestion_run)
            await self.db.commit()
            await self.db.refresh(ingestion_run)

            logger.info(f"Created ingestion run with ID={ingestion_run.id}")
            return ingestion_run

        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to create ingestion run: {str(e)}")
            raise

    async def update_ingestion_run(
        self,
        run_id: int,
        status: str | None = None,
        items_processed: int | None = None,
        items_new: int | None = None,
        items_updated: int | None = None,
        items_failed: int | None = None,
        errors_count: int | None = None,
        error_notes: str | None = None,
        notes: dict[str, Any] | None = None,
        completed_at: datetime | None = None,
    ) -> IngestionRun | None:
        """
        Update an existing ingestion run with new information.

        Args:
            run_id: ID of the ingestion run to update
            status: New status ('started', 'running', 'completed', 'failed')
            items_processed: Total number of items processed
            items_new: Number of new items created
            items_updated: Number of existing items updated
            items_failed: Number of items that failed processing
            errors_count: Total number of errors encountered
            error_notes: Detailed error information
            notes: Additional metadata as JSON
            completed_at: When the run completed (auto-set if status is completed/failed)

        Returns:
            Updated IngestionRun instance or None if not found

        Raises:
            SQLAlchemyError: If database operation fails
        """
        logger.info(f"Updating ingestion run ID={run_id}")

        try:
            # Get the existing run
            stmt = select(IngestionRun).where(IngestionRun.id == run_id)
            result = await self.db.execute(stmt)
            ingestion_run = result.scalar_one_or_none()

            if not ingestion_run:
                logger.warning(f"Ingestion run ID={run_id} not found")
                return None

            # Update fields if provided
            if status is not None:
                ingestion_run.status = status

            if items_processed is not None:
                ingestion_run.items_processed = items_processed

            if items_new is not None:
                ingestion_run.items_new = items_new

            if items_updated is not None:
                ingestion_run.items_updated = items_updated

            if items_failed is not None:
                ingestion_run.items_failed = items_failed

            if errors_count is not None:
                ingestion_run.errors_count = errors_count

            if error_notes is not None:
                ingestion_run.error_notes = error_notes

            if notes is not None:
                # Merge with existing notes
                existing_notes = ingestion_run.notes or {}
                existing_notes.update(notes)
                ingestion_run.notes = existing_notes

            # Auto-set completed_at if status indicates completion
            if status in ("completed", "failed") and completed_at is None:
                completed_at = datetime.now(UTC)

            if completed_at is not None:
                ingestion_run.completed_at = completed_at

            await self.db.commit()
            await self.db.refresh(ingestion_run)

            logger.info(
                f"Updated ingestion run ID={run_id}, status={ingestion_run.status}, "
                f"processed={ingestion_run.items_processed}",
            )

            return ingestion_run

        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to update ingestion run ID={run_id}: {str(e)}")
            raise

    async def complete_ingestion_run(
        self,
        run_id: int,
        upsert_stats: dict[str, int],
        errors_count: int = 0,
        error_notes: str | None = None,
        notes: dict[str, Any] | None = None,
    ) -> IngestionRun | None:
        """
        Mark an ingestion run as completed with final statistics.

        Args:
            run_id: ID of the ingestion run
            upsert_stats: Dictionary with 'new', 'updated', 'failed' counts
            errors_count: Total number of errors
            error_notes: Detailed error information
            notes: Additional metadata

        Returns:
            Updated IngestionRun instance or None if not found
        """
        total_processed = sum(upsert_stats.values())
        status = "completed" if upsert_stats["failed"] == 0 else "failed"

        return await self.update_ingestion_run(
            run_id=run_id,
            status=status,
            items_processed=total_processed,
            items_new=upsert_stats["new"],
            items_updated=upsert_stats["updated"],
            items_failed=upsert_stats["failed"],
            errors_count=errors_count,
            error_notes=error_notes,
            notes=notes,
            completed_at=datetime.now(UTC),
        )

    async def get_ingestion_runs(
        self,
        source_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IngestionRun]:
        """
        Query ingestion runs with optional filtering.

        Args:
            source_id: Filter by source ID
            status: Filter by status
            limit: Maximum number of runs to return
            offset: Number of runs to skip

        Returns:
            List of IngestionRun instances
        """
        logger.info(f"Querying ingestion runs: source_id={source_id}, status={status}, limit={limit}, offset={offset}")

        try:
            stmt = select(IngestionRun).order_by(IngestionRun.started_at.desc())

            if source_id is not None:
                stmt = stmt.where(IngestionRun.source_id == source_id)

            if status is not None:
                stmt = stmt.where(IngestionRun.status == status)

            stmt = stmt.limit(limit).offset(offset)

            result = await self.db.execute(stmt)
            runs = result.scalars().all()

            logger.info(f"Found {len(runs)} ingestion runs")
            return list(runs)

        except SQLAlchemyError as e:
            logger.error(f"Failed to query ingestion runs: {str(e)}")
            return []

    async def get_latest_ingestion_run(self, source_id: int, status: str | None = None) -> IngestionRun | None:
        """
        Get the most recent ingestion run for a source.

        Args:
            source_id: ID of the source
            status: Optional status filter

        Returns:
            Latest IngestionRun instance or None
        """
        try:
            stmt = (
                select(IngestionRun)
                .where(IngestionRun.source_id == source_id)
                .order_by(IngestionRun.started_at.desc())
                .limit(1)
            )

            if status is not None:
                stmt = stmt.where(IngestionRun.status == status)

            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(f"Failed to get latest ingestion run: {str(e)}")
            return None

    async def get_ingestion_stats(self, source_id: int | None = None, hours: int = 24) -> dict[str, Any]:
        """
        Get aggregated ingestion statistics for monitoring.

        Args:
            source_id: Optional source ID filter
            hours: Number of hours to look back

        Returns:
            Dictionary with aggregated statistics
        """
        try:
            # Base query for recent runs
            cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

            stmt = select(
                func.count(IngestionRun.id).label("total_runs"),
                func.sum(IngestionRun.items_processed).label("total_processed"),
                func.sum(IngestionRun.items_new).label("total_new"),
                func.sum(IngestionRun.items_updated).label("total_updated"),
                func.sum(IngestionRun.items_failed).label("total_failed"),
                func.sum(IngestionRun.errors_count).label("total_errors"),
                func.sum(case((IngestionRun.status == "completed", 1), else_=0)).label("successful_runs"),
                func.sum(case((IngestionRun.status == "failed", 1), else_=0)).label("failed_runs"),
            ).where(IngestionRun.started_at >= cutoff_time)

            if source_id is not None:
                stmt = stmt.where(IngestionRun.source_id == source_id)

            result = await self.db.execute(stmt)
            row = result.first()

            if row:
                return {
                    "total_runs": row.total_runs or 0,
                    "total_processed": row.total_processed or 0,
                    "total_new": row.total_new or 0,
                    "total_updated": row.total_updated or 0,
                    "total_failed": row.total_failed or 0,
                    "total_errors": row.total_errors or 0,
                    "successful_runs": row.successful_runs or 0,
                    "failed_runs": row.failed_runs or 0,
                    "success_rate": ((row.successful_runs or 0) / max(row.total_runs or 1, 1) * 100),
                    "hours_covered": hours,
                }

            return {
                "total_runs": 0,
                "total_processed": 0,
                "total_new": 0,
                "total_updated": 0,
                "total_failed": 0,
                "total_errors": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "success_rate": 0.0,
                "hours_covered": hours,
            }

        except SQLAlchemyError as e:
            logger.error(f"Failed to get ingestion stats: {str(e)}")
            return {}


# Convenience functions for dependency injection
async def get_ingestion_service(db: AsyncSession) -> IngestionService:
    """Factory function to create IngestionService instance."""
    return IngestionService(db)
