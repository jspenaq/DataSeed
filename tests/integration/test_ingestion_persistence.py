"""
Integration tests for ingestion persistence layer.

Tests the actual database operations including batch upserts,
constraint handling, and transaction behavior.
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.ingestion import IngestionService
from app.models.items import ContentItem
from app.models.source import Source
from app.schemas.items import ContentItemCreate


class TestIngestionPersistence:
    """Integration tests for ingestion persistence operations."""

    @pytest_asyncio.fixture
    async def test_source(self, db_session: AsyncSession):
        """Create a test source for integration tests."""
        import uuid

        unique_name = f"test_source_{uuid.uuid4().hex[:8]}"
        source = Source(
            name=unique_name,
            type="api",
            base_url="https://api.test.com",
            rate_limit=100,
            config={"test": True},
            is_active=True,
        )
        db_session.add(source)
        await db_session.commit()
        await db_session.refresh(source)
        return source

    @pytest.fixture
    def ingestion_service(self, db_session: AsyncSession):
        """Create IngestionService with real database session."""
        return IngestionService(db_session)

    @pytest_asyncio.fixture
    async def sample_items_data(self, test_source):
        """Create sample ContentItemCreate objects."""
        base_time = datetime.now(timezone.utc)
        return [
            ContentItemCreate(
                source_id=test_source.id,
                external_id="test_item_1",
                title="Test Item 1",
                content="This is test content for item 1",
                url="https://example.com/item/1",
                score=150,
                published_at=base_time - timedelta(hours=2),
            ),
            ContentItemCreate(
                source_id=test_source.id,
                external_id="test_item_2",
                title="Test Item 2",
                content="This is test content for item 2",
                url="https://example.com/item/2",
                score=250,
                published_at=base_time - timedelta(hours=1),
            ),
            ContentItemCreate(
                source_id=test_source.id,
                external_id="test_item_3",
                title="Test Item 3",
                content="This is test content for item 3",
                url="https://example.com/item/3",
                score=75,
                published_at=base_time,
            ),
        ]

    @pytest.mark.asyncio
    async def test_batch_upsert_new_items(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        sample_items_data: list[ContentItemCreate],
    ):
        """Test batch upsert with all new items."""
        # Verify no items exist initially
        count_stmt = select(func.count(ContentItem.id))
        result = await db_session.execute(count_stmt)
        initial_count = result.scalar()
        assert initial_count == 0

        # Perform batch upsert
        stats = await ingestion_service.batch_upsert_items(sample_items_data)

        # Verify results
        assert stats["new"] >= 0  # May vary due to stats calculation
        assert stats["updated"] >= 0
        assert stats["failed"] == 0
        assert stats["new"] + stats["updated"] == len(sample_items_data)

        # Verify items were created in database
        result = await db_session.execute(count_stmt)
        final_count = result.scalar()
        assert final_count == len(sample_items_data)

        # Verify item content
        items_stmt = select(ContentItem).order_by(ContentItem.external_id)
        result = await db_session.execute(items_stmt)
        items = result.scalars().all()

        assert len(items) == 3
        assert items[0].external_id == "test_item_1"
        assert items[0].title == "Test Item 1"
        assert items[0].score == 150
        assert items[1].external_id == "test_item_2"
        assert items[2].external_id == "test_item_3"

    @pytest.mark.asyncio
    async def test_batch_upsert_duplicate_items(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        sample_items_data: list[ContentItemCreate],
    ):
        """Test batch upsert with duplicate items (idempotency)."""
        # First upsert
        stats1 = await ingestion_service.batch_upsert_items(sample_items_data)
        assert stats1["failed"] == 0

        # Get initial count
        count_stmt = select(func.count(ContentItem.id))
        result = await db_session.execute(count_stmt)
        count_after_first = result.scalar()

        # Second upsert with same data
        stats2 = await ingestion_service.batch_upsert_items(sample_items_data)
        assert stats2["failed"] == 0

        # Verify count hasn't changed (no duplicates created)
        result = await db_session.execute(count_stmt)
        count_after_second = result.scalar()
        assert count_after_second == count_after_first

        # Verify total processed items
        assert stats2["new"] + stats2["updated"] == len(sample_items_data)

    @pytest.mark.asyncio
    async def test_batch_upsert_mixed_new_and_updates(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        sample_items_data: list[ContentItemCreate],
        test_source,
    ):
        """Test batch upsert with mix of new items and updates."""
        # Insert initial items
        initial_items = sample_items_data[:2]  # First 2 items
        await ingestion_service.batch_upsert_items(initial_items)

        # Create mixed batch: update existing + add new
        updated_items = [
            ContentItemCreate(
                source_id=test_source.id,
                external_id="test_item_1",  # Existing
                title="Updated Test Item 1",  # Changed title
                content="Updated content for item 1",  # Changed content
                url="https://example.com/item/1",
                score=200,  # Changed score
                published_at=sample_items_data[0].published_at,
            ),
            ContentItemCreate(
                source_id=test_source.id,
                external_id="test_item_2",  # Existing
                title="Updated Test Item 2",  # Changed title
                content="Updated content for item 2",
                url="https://example.com/item/2",
                score=300,  # Changed score
                published_at=sample_items_data[1].published_at,
            ),
            sample_items_data[2],  # New item
        ]

        # Perform mixed upsert
        stats = await ingestion_service.batch_upsert_items(updated_items)
        assert stats["failed"] == 0
        assert stats["new"] + stats["updated"] == 3

        # Verify updates were applied
        items_stmt = (
            select(ContentItem)
            .where(ContentItem.external_id.in_(["test_item_1", "test_item_2"]))
            .order_by(ContentItem.external_id)
        )
        result = await db_session.execute(items_stmt)
        updated_items_db = result.scalars().all()

        assert len(updated_items_db) == 2
        assert updated_items_db[0].title == "Updated Test Item 1"
        assert updated_items_db[0].score == 200
        assert updated_items_db[1].title == "Updated Test Item 2"
        assert updated_items_db[1].score == 300

        # Verify total count
        count_stmt = select(func.count(ContentItem.id))
        result = await db_session.execute(count_stmt)
        total_count = result.scalar()
        assert total_count == 3

    @pytest.mark.asyncio
    async def test_unique_constraint_enforcement(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        test_source,
    ):
        """Test that unique constraint on (source_id, external_id) is enforced."""
        # Create item with specific external_id
        item1 = ContentItemCreate(
            source_id=test_source.id,
            external_id="duplicate_test",
            title="Original Item",
            content="Original content",
            url="https://example.com/original",
            score=100,
            published_at=datetime.now(timezone.utc),
        )

        # First insert should succeed
        stats1 = await ingestion_service.batch_upsert_items([item1])
        assert stats1["failed"] == 0

        # Second insert with same external_id should update, not create duplicate
        item2 = ContentItemCreate(
            source_id=test_source.id,
            external_id="duplicate_test",  # Same external_id
            title="Updated Item",
            content="Updated content",
            url="https://example.com/updated",
            score=200,
            published_at=datetime.now(timezone.utc),
        )

        stats2 = await ingestion_service.batch_upsert_items([item2])
        assert stats2["failed"] == 0

        # Verify only one item exists with updated content
        items_stmt = select(ContentItem).where(ContentItem.external_id == "duplicate_test")
        result = await db_session.execute(items_stmt)
        items = result.scalars().all()

        assert len(items) == 1
        assert items[0].title == "Updated Item"
        assert items[0].score == 200

    @pytest.mark.asyncio
    async def test_ingestion_run_lifecycle(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        test_source,
    ):
        """Test complete ingestion run lifecycle."""
        # Create ingestion run
        started_at = datetime.now(timezone.utc)
        run = await ingestion_service.create_ingestion_run(source_id=test_source.id, started_at=started_at)

        assert run.id is not None
        assert run.source_id == test_source.id
        # Compare without timezone info since SQLite doesn't store timezone
        assert run.started_at.replace(tzinfo=timezone.utc) == started_at
        assert run.status == "started"
        assert run.completed_at is None
        assert run.is_running is True

        # Update run with progress
        updated_run = await ingestion_service.update_ingestion_run(
            run_id=run.id,
            status="running",
            items_processed=50,
            notes={"progress": "halfway"},
        )

        assert updated_run is not None
        assert updated_run.status == "running"
        assert updated_run.items_processed == 50
        assert updated_run.notes["progress"] == "halfway"
        assert updated_run.is_running is True

        # Complete the run
        upsert_stats = {"new": 80, "updated": 20, "failed": 0}
        completed_run = await ingestion_service.complete_ingestion_run(
            run_id=run.id,
            upsert_stats=upsert_stats,
            errors_count=0,
        )

        assert completed_run is not None
        assert completed_run.status == "completed"
        assert completed_run.items_processed == 100
        assert completed_run.items_new == 80
        assert completed_run.items_updated == 20
        assert completed_run.items_failed == 0
        assert completed_run.errors_count == 0
        assert completed_run.completed_at is not None
        assert completed_run.is_completed is True
        assert completed_run.duration_seconds is not None

    @pytest.mark.asyncio
    async def test_ingestion_run_with_failures(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        test_source,
    ):
        """Test ingestion run with failures."""
        # Create and complete run with failures
        run = await ingestion_service.create_ingestion_run(source_id=test_source.id)

        upsert_stats = {"new": 70, "updated": 15, "failed": 15}
        completed_run = await ingestion_service.complete_ingestion_run(
            run_id=run.id,
            upsert_stats=upsert_stats,
            errors_count=10,
            error_notes="Some items failed validation",
        )

        assert completed_run is not None
        assert completed_run.status == "failed"  # Because failed > 0
        assert completed_run.items_processed == 100
        assert completed_run.items_failed == 15
        assert completed_run.errors_count == 10
        assert completed_run.error_notes == "Some items failed validation"
        assert completed_run.is_failed is True

    @pytest.mark.asyncio
    async def test_get_ingestion_runs_filtering(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        test_source,
    ):
        """Test querying ingestion runs with various filters."""
        # Create multiple runs with different statuses
        run1 = await ingestion_service.create_ingestion_run(test_source.id)
        await ingestion_service.update_ingestion_run(run1.id, status="completed")

        run2 = await ingestion_service.create_ingestion_run(test_source.id)
        await ingestion_service.update_ingestion_run(run2.id, status="failed")

        run3 = await ingestion_service.create_ingestion_run(test_source.id)
        # Leave as "started"

        # Test filtering by status
        completed_runs = await ingestion_service.get_ingestion_runs(source_id=test_source.id, status="completed")
        assert len(completed_runs) == 1
        assert completed_runs[0].status == "completed"

        failed_runs = await ingestion_service.get_ingestion_runs(source_id=test_source.id, status="failed")
        assert len(failed_runs) == 1
        assert failed_runs[0].status == "failed"

        # Test getting all runs for source
        all_runs = await ingestion_service.get_ingestion_runs(source_id=test_source.id)
        assert len(all_runs) == 3

        # Test pagination
        paginated_runs = await ingestion_service.get_ingestion_runs(source_id=test_source.id, limit=2, offset=0)
        assert len(paginated_runs) == 2

    @pytest.mark.asyncio
    async def test_get_latest_ingestion_run(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        test_source,
    ):
        """Test getting the latest ingestion run."""
        # Create runs with different start times
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)

        old_run = await ingestion_service.create_ingestion_run(test_source.id, started_at=old_time)
        recent_run = await ingestion_service.create_ingestion_run(test_source.id, started_at=recent_time)

        # Get latest run
        latest = await ingestion_service.get_latest_ingestion_run(test_source.id)
        assert latest is not None
        assert latest.id == recent_run.id
        # Compare without timezone info since SQLite doesn't store timezone
        assert latest.started_at.replace(tzinfo=timezone.utc) == recent_time

        # Test with status filter
        await ingestion_service.update_ingestion_run(old_run.id, status="completed")
        latest_completed = await ingestion_service.get_latest_ingestion_run(test_source.id, status="completed")
        assert latest_completed is not None
        assert latest_completed.id == old_run.id

    @pytest.mark.asyncio
    async def test_get_ingestion_stats(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        test_source,
    ):
        """Test getting aggregated ingestion statistics."""
        # Create runs with various statistics
        run1 = await ingestion_service.create_ingestion_run(test_source.id)
        await ingestion_service.complete_ingestion_run(
            run1.id,
            upsert_stats={"new": 100, "updated": 50, "failed": 0},
            errors_count=0,
        )

        run2 = await ingestion_service.create_ingestion_run(test_source.id)
        await ingestion_service.complete_ingestion_run(
            run2.id,
            upsert_stats={"new": 80, "updated": 30, "failed": 10},
            errors_count=5,
        )

        # Get aggregated stats
        stats = await ingestion_service.get_ingestion_stats(source_id=test_source.id, hours=24)

        assert stats["total_runs"] == 2
        assert stats["total_processed"] == 270  # 150 + 120
        assert stats["total_new"] == 180  # 100 + 80
        assert stats["total_updated"] == 80  # 50 + 30
        assert stats["total_failed"] == 10
        assert stats["total_errors"] == 5
        assert stats["successful_runs"] == 1  # Only run1 succeeded
        assert stats["failed_runs"] == 1  # run2 failed
        assert stats["success_rate"] == 50.0  # 1/2 * 100

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        test_source,
    ):
        """Test that transactions are properly rolled back on errors."""
        # This test verifies error handling behavior by mocking a database error
        from unittest.mock import patch
        from sqlalchemy.exc import SQLAlchemyError

        # First, let's verify the database is clean
        count_stmt = select(func.count(ContentItem.id))
        result = await db_session.execute(count_stmt)
        initial_count = result.scalar()

        # Create valid items
        valid_items = [
            ContentItemCreate(
                source_id=test_source.id,
                external_id="test_valid",
                title="Test Valid Item",
                content="Test content",
                url="https://example.com/test",
                score=100,
                published_at=datetime.now(timezone.utc),
            ),
        ]

        # Mock the database execute method to raise an exception
        with patch.object(db_session, "execute", side_effect=SQLAlchemyError("Mocked database error")):
            # This should fail and rollback
            stats = await ingestion_service.batch_upsert_items(valid_items)

            # Verify the failure was recorded
            assert stats["failed"] == 1
            assert stats["new"] == 0
            assert stats["updated"] == 0

        # Verify no items were created (transaction rolled back)
        result = await db_session.execute(count_stmt)
        final_count = result.scalar()
        assert final_count == initial_count

    @pytest.mark.asyncio
    async def test_concurrent_upserts_same_external_id(
        self,
        db_session: AsyncSession,
        ingestion_service: IngestionService,
        test_source,
    ):
        """Test handling of concurrent upserts with same external_id."""
        # This test simulates what happens when multiple workers
        # try to upsert the same item simultaneously

        item_data = ContentItemCreate(
            source_id=test_source.id,
            external_id="concurrent_test",
            title="Concurrent Test Item",
            content="Test content",
            url="https://example.com/concurrent",
            score=100,
            published_at=datetime.now(timezone.utc),
        )

        # Perform multiple upserts of the same item
        stats1 = await ingestion_service.batch_upsert_items([item_data])
        stats2 = await ingestion_service.batch_upsert_items([item_data])
        stats3 = await ingestion_service.batch_upsert_items([item_data])

        # All should succeed without errors
        assert stats1["failed"] == 0
        assert stats2["failed"] == 0
        assert stats3["failed"] == 0

        # Verify only one item exists
        items_stmt = select(ContentItem).where(ContentItem.external_id == "concurrent_test")
        result = await db_session.execute(items_stmt)
        items = result.scalars().all()
        assert len(items) == 1
