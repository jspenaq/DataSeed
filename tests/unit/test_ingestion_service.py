"""
Unit tests for the ingestion service.

Tests the core persistence functionality including batch upserts,
ingestion run tracking, and error handling.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.services.ingestion import IngestionService
from app.models.ingestion import IngestionRun
from app.schemas.items import ContentItemCreate

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio


class TestIngestionService:
    """Test suite for IngestionService class."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def ingestion_service(self, mock_db_session):
        """Create an IngestionService instance with mocked database."""
        return IngestionService(mock_db_session)

    @pytest.fixture
    def sample_items(self):
        """Create sample ContentItemCreate objects for testing."""
        return [
            ContentItemCreate(
                source_id=1,
                external_id="item_1",
                title="Test Item 1",
                content="Test content 1",
                url="https://example.com/1",
                score=100,
                published_at=datetime.utcnow(),
            ),
            ContentItemCreate(
                source_id=1,
                external_id="item_2",
                title="Test Item 2",
                content="Test content 2",
                url="https://example.com/2",
                score=200,
                published_at=datetime.utcnow(),
            ),
        ]

    async def test_batch_upsert_items_empty_list(self, ingestion_service):
        """Test batch upsert with empty list returns zero counts."""
        result = await ingestion_service.batch_upsert_items([])

        assert result == {"new": 0, "updated": 0, "failed": 0}

    async def test_batch_upsert_items_success(self, ingestion_service, mock_db_session, sample_items):
        """Test successful batch upsert operation."""
        # Mock the execute result
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db_session.execute.return_value = mock_result

        # Mock the stats calculation
        with patch.object(
            ingestion_service,
            "_calculate_upsert_stats",
            return_value=(2, 0),  # 2 new, 0 updated
        ):
            result = await ingestion_service.batch_upsert_items(sample_items)

        assert result == {"new": 2, "updated": 0, "failed": 0}
        mock_db_session.execute.assert_called_once()
        mock_db_session.commit.assert_called_once()

    async def test_batch_upsert_items_database_error(self, ingestion_service, mock_db_session, sample_items):
        """Test batch upsert handles database errors gracefully."""
        # Mock database error
        mock_db_session.execute.side_effect = SQLAlchemyError("Database error")

        result = await ingestion_service.batch_upsert_items(sample_items)

        assert result == {"new": 0, "updated": 0, "failed": 2}
        mock_db_session.rollback.assert_called_once()

    async def test_create_ingestion_run_success(self, ingestion_service, mock_db_session):
        """Test successful creation of ingestion run."""
        source_id = 1
        started_at = datetime.utcnow()

        # Mock the created run
        mock_run = IngestionRun(id=1, source_id=source_id, started_at=started_at, status="started")
        mock_db_session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 1))

        result = await ingestion_service.create_ingestion_run(source_id=source_id, started_at=started_at)

        assert result.source_id == source_id
        assert result.started_at == started_at
        assert result.status == "started"
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    async def test_create_ingestion_run_database_error(self, ingestion_service, mock_db_session):
        """Test ingestion run creation handles database errors."""
        mock_db_session.commit.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError):
            await ingestion_service.create_ingestion_run(source_id=1)

        mock_db_session.rollback.assert_called_once()

    async def test_update_ingestion_run_success(self, ingestion_service, mock_db_session):
        """Test successful update of ingestion run."""
        run_id = 1

        # Mock existing run
        mock_run = IngestionRun(id=run_id, source_id=1, started_at=datetime.utcnow(), status="started")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_db_session.execute.return_value = mock_result

        result = await ingestion_service.update_ingestion_run(
            run_id=run_id,
            status="completed",
            items_processed=100,
            items_new=80,
            items_updated=20,
        )

        assert result.status == "completed"
        assert result.items_processed == 100
        assert result.items_new == 80
        assert result.items_updated == 20
        assert result.completed_at is not None
        mock_db_session.commit.assert_called_once()

    async def test_update_ingestion_run_not_found(self, ingestion_service, mock_db_session):
        """Test update of non-existent ingestion run."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await ingestion_service.update_ingestion_run(run_id=999, status="completed")

        assert result is None

    async def test_complete_ingestion_run(self, ingestion_service, mock_db_session):
        """Test completing an ingestion run with statistics."""
        run_id = 1
        upsert_stats = {"new": 80, "updated": 20, "failed": 0}

        # Mock existing run
        mock_run = IngestionRun(id=run_id, source_id=1, started_at=datetime.utcnow(), status="started")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_db_session.execute.return_value = mock_result

        result = await ingestion_service.complete_ingestion_run(
            run_id=run_id,
            upsert_stats=upsert_stats,
            errors_count=0,
        )

        assert result.status == "completed"
        assert result.items_processed == 100  # 80 + 20 + 0
        assert result.items_new == 80
        assert result.items_updated == 20
        assert result.items_failed == 0
        assert result.errors_count == 0

    async def test_complete_ingestion_run_with_failures(self, ingestion_service, mock_db_session):
        """Test completing an ingestion run with failures."""
        run_id = 1
        upsert_stats = {"new": 70, "updated": 20, "failed": 10}

        # Mock existing run
        mock_run = IngestionRun(id=run_id, source_id=1, started_at=datetime.utcnow(), status="started")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_db_session.execute.return_value = mock_result

        result = await ingestion_service.complete_ingestion_run(
            run_id=run_id,
            upsert_stats=upsert_stats,
            errors_count=5,
            error_notes="Some items failed validation",
        )

        assert result.status == "failed"  # Because failed > 0
        assert result.items_processed == 100
        assert result.items_failed == 10
        assert result.errors_count == 5
        assert result.error_notes == "Some items failed validation"

    async def test_get_ingestion_runs_with_filters(self, ingestion_service, mock_db_session):
        """Test querying ingestion runs with filters."""
        # Mock query results
        mock_runs = [
            IngestionRun(id=1, source_id=1, started_at=datetime.utcnow()),
            IngestionRun(id=2, source_id=1, started_at=datetime.utcnow()),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_runs
        mock_db_session.execute.return_value = mock_result

        result = await ingestion_service.get_ingestion_runs(source_id=1, status="completed", limit=10, offset=0)

        assert len(result) == 2
        assert all(isinstance(run, IngestionRun) for run in result)
        mock_db_session.execute.assert_called_once()

    async def test_get_latest_ingestion_run(self, ingestion_service, mock_db_session):
        """Test getting the latest ingestion run for a source."""
        mock_run = IngestionRun(id=1, source_id=1, started_at=datetime.utcnow(), status="completed")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_db_session.execute.return_value = mock_result

        result = await ingestion_service.get_latest_ingestion_run(source_id=1, status="completed")

        assert result == mock_run
        mock_db_session.execute.assert_called_once()

    async def test_get_ingestion_stats(self, ingestion_service, mock_db_session):
        """Test getting aggregated ingestion statistics."""
        # Mock aggregated results
        mock_row = MagicMock()
        mock_row.total_runs = 10
        mock_row.total_processed = 1000
        mock_row.total_new = 800
        mock_row.total_updated = 200
        mock_row.total_failed = 0
        mock_row.total_errors = 0
        mock_row.successful_runs = 10
        mock_row.failed_runs = 0

        mock_result = MagicMock()
        mock_result.first.return_value = mock_row
        mock_db_session.execute.return_value = mock_result

        result = await ingestion_service.get_ingestion_stats(source_id=1, hours=24)

        assert result["total_runs"] == 10
        assert result["total_processed"] == 1000
        assert result["success_rate"] == 100.0
        assert result["hours_covered"] == 24
        mock_db_session.execute.assert_called_once()

    async def test_calculate_upsert_stats(self, ingestion_service, mock_db_session):
        """Test calculation of upsert statistics."""
        items_data = [
            {"source_id": 1, "external_id": "item_1"},
            {"source_id": 1, "external_id": "item_2"},
            {"source_id": 1, "external_id": "item_3"},
        ]
        total_affected = 3

        # Mock existing count query
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1  # 1 existing item
        mock_db_session.execute.return_value = mock_result

        new_count, updated_count = await ingestion_service._calculate_upsert_stats(items_data, total_affected)

        assert new_count == 2  # 3 total - 1 existing
        assert updated_count == 1  # 1 existing
        mock_db_session.execute.assert_called_once()

    async def test_calculate_upsert_stats_error_fallback(self, ingestion_service, mock_db_session):
        """Test upsert stats calculation fallback on error."""
        items_data = [{"source_id": 1, "external_id": "item_1"}]
        total_affected = 1

        # Mock database error
        mock_db_session.execute.side_effect = SQLAlchemyError("Query error")

        new_count, updated_count = await ingestion_service._calculate_upsert_stats(items_data, total_affected)

        # Should fallback to assuming all are new
        assert new_count == 1
        assert updated_count == 0


class TestIngestionRunModel:
    """Test suite for IngestionRun model properties."""

    def test_duration_seconds_completed(self):
        """Test duration calculation for completed run."""
        started = datetime.utcnow()
        completed = started + timedelta(seconds=120)

        run = IngestionRun(source_id=1, started_at=started, completed_at=completed, status="completed")

        assert run.duration_seconds == 120.0

    def test_duration_seconds_not_completed(self):
        """Test duration calculation for incomplete run."""
        run = IngestionRun(source_id=1, started_at=datetime.utcnow(), status="started")

        assert run.duration_seconds is None

    def test_is_running_property(self):
        """Test is_running property for different statuses."""
        run = IngestionRun(source_id=1, started_at=datetime.utcnow())

        run.status = "started"
        assert run.is_running is True

        run.status = "running"
        assert run.is_running is True

        run.status = "completed"
        assert run.is_running is False

        run.status = "failed"
        assert run.is_running is False

    def test_is_completed_property(self):
        """Test is_completed property."""
        run = IngestionRun(source_id=1, started_at=datetime.utcnow())

        run.status = "completed"
        assert run.is_completed is True

        run.status = "started"
        assert run.is_completed is False

    def test_is_failed_property(self):
        """Test is_failed property."""
        run = IngestionRun(source_id=1, started_at=datetime.utcnow())

        run.status = "failed"
        assert run.is_failed is True

        run.status = "completed"
        assert run.is_failed is False
