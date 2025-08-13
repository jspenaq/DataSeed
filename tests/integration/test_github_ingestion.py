"""
Integration tests for GitHub ingestion pipeline.

Tests the complete end-to-end flow: ingest_source_task -> IngestionService ->
GitHubExtractor -> GitHubNormalizer -> Database persistence.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.ingestion import IngestionService
from app.models.ingestion import IngestionRun
from app.models.items import ContentItem
from app.models.source import Source
from app.workers.tasks import _ingest_source_async

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio


class TestGitHubIngestionIntegration:
    @pytest.fixture
    def mock_github_http_client(self, sample_github_search_response):
        """Create a properly mocked HTTP client for GitHub."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_github_search_response
        mock_response.headers = {"ETag": "test-etag"}
        mock_client.get_with_response.return_value = mock_response
        mock_client.default_headers = {}
        mock_client.close = AsyncMock()
        return mock_client

    """Integration tests for GitHub ingestion pipeline."""

    @pytest_asyncio.fixture
    async def github_search_source(self, db_session: AsyncSession):
        """Create a GitHub source configured for search mode."""
        source = Source(
            name="github",  # Use the registered extractor name
            type="api",
            base_url="https://api.github.com",
            rate_limit=5000,
            config={"token": "test_github_token", "search_endpoint": "/search/repositories", "mode": "search"},
            is_active=True,
        )
        db_session.add(source)
        await db_session.commit()
        await db_session.refresh(source)
        return source

    @pytest_asyncio.fixture
    async def github_releases_source(self, db_session: AsyncSession):
        """Create a GitHub source configured for releases mode."""
        source = Source(
            name="github",  # Use the registered extractor name
            type="api",
            base_url="https://api.github.com",
            rate_limit=5000,
            config={
                "token": "test_github_token",
                "mode": "releases",
                "repositories": ["facebook/react", "microsoft/vscode"],
            },
            is_active=True,
        )
        db_session.add(source)
        await db_session.commit()
        await db_session.refresh(source)
        return source

    @pytest.fixture
    def sample_github_search_response(self):
        """Sample GitHub search API response."""
        return {
            "total_count": 2,
            "incomplete_results": False,
            "items": [
                {
                    "id": 123456,
                    "full_name": "test/awesome-project",
                    "html_url": "https://github.com/test/awesome-project",
                    "description": "An awesome test project for integration testing",
                    "stargazers_count": 1250,
                    "pushed_at": "2023-12-01T10:00:00Z",
                    "updated_at": "2023-12-01T10:00:00Z",
                    "language": "Python",
                    "topics": ["testing", "integration", "python"],
                },
                {
                    "id": 789012,
                    "full_name": "example/cool-library",
                    "html_url": "https://github.com/example/cool-library",
                    "description": "A cool library for developers",
                    "stargazers_count": 850,
                    "pushed_at": "2023-12-01T11:30:00Z",
                    "updated_at": "2023-12-01T11:30:00Z",
                    "language": "JavaScript",
                    "topics": ["library", "javascript", "npm"],
                },
            ],
        }

    @pytest.fixture
    def sample_github_releases_response(self):
        """Sample GitHub releases API response."""
        # Use recent dates so they won't be filtered out by the "since" parameter
        from datetime import datetime, timedelta

        recent_date1 = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        recent_date2 = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        return [
            {
                "id": 111111,
                "name": "React v18.2.0",
                "tag_name": "v18.2.0",
                "html_url": "https://github.com/facebook/react/releases/tag/v18.2.0",
                "body": "This release includes important bug fixes and performance improvements.",
                "published_at": recent_date1,
                "prerelease": False,
                "draft": False,
            },
            {
                "id": 222222,
                "name": "React v18.2.1",
                "tag_name": "v18.2.1",
                "html_url": "https://github.com/facebook/react/releases/tag/v18.2.1",
                "body": "Patch release with critical bug fixes.",
                "published_at": recent_date2,
                "prerelease": False,
                "draft": False,
            },
        ]

    @pytest.fixture
    def mock_task_instance(self, db_session: AsyncSession):
        """Create a mock Celery task instance."""
        task_instance = MagicMock()
        task_instance.db_session = db_session
        return task_instance

    async def test_github_search_ingestion_end_to_end(
        self,
        db_session: AsyncSession,
        github_search_source: Source,
        sample_github_search_response: dict,
        mock_task_instance,
        mock_github_http_client,
    ):
        """Test complete GitHub search mode ingestion pipeline (mocking HTTP client)."""
        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # No cached ETag
        mock_redis.setex.return_value = True

        # Verify initial state - no items in database
        count_stmt = select(func.count(ContentItem.id))
        result = await db_session.execute(count_stmt)
        initial_count = result.scalar()
        assert initial_count == 0

        # Verify no ingestion runs initially
        runs_stmt = select(func.count(IngestionRun.id))
        result = await db_session.execute(runs_stmt)
        initial_runs = result.scalar()
        assert initial_runs == 0

        # Patch the HTTP client in the extractor
        from app.core.extractors.github import GitHubExtractor

        with patch.object(GitHubExtractor, "get_http_client", return_value=mock_github_http_client):
            with patch("app.core.extractors.github.RedisClient.get_redis", return_value=mock_redis):
                # Run the ingestion task
                result = await _ingest_source_async(mock_task_instance, github_search_source.name)

        # Verify task result
        assert result["processed"] == 2
        assert result["new"] == 2
        assert result["updated"] == 0
        assert result["errors"] == 0

        # Verify items were created in database
        result = await db_session.execute(count_stmt)
        final_count = result.scalar()
        assert final_count == 2

        # Verify item content
        items_stmt = select(ContentItem).order_by(ContentItem.external_id)
        result = await db_session.execute(items_stmt)
        items = result.scalars().all()

        assert len(items) == 2

        # Check first item
        item1 = items[0]
        assert item1.source_id == github_search_source.id
        assert item1.external_id == "123456"
        assert item1.title == "test/awesome-project"
        assert item1.content == "An awesome test project for integration testing"
        assert item1.url == "https://github.com/test/awesome-project"
        assert item1.score == 1250
        assert item1.published_at == datetime(2023, 12, 1, 10, 0, 0)

        # Check second item
        item2 = items[1]
        assert item2.source_id == github_search_source.id
        assert item2.external_id == "789012"
        assert item2.title == "example/cool-library"
        assert item2.content == "A cool library for developers"
        assert item2.url == "https://github.com/example/cool-library"
        assert item2.score == 850
        assert item2.published_at == datetime(2023, 12, 1, 11, 30, 0)

        # Verify ingestion run was created and completed
        runs_stmt = select(IngestionRun).where(IngestionRun.source_id == github_search_source.id)
        result = await db_session.execute(runs_stmt)
        runs = result.scalars().all()

        assert len(runs) == 1
        run = runs[0]
        assert run.status == "completed"
        assert run.items_processed == 2
        assert run.items_new == 2
        assert run.items_updated == 0
        assert run.items_failed == 0
        assert run.errors_count == 0
        assert run.completed_at is not None

    async def test_github_releases_ingestion_end_to_end(
        self,
        db_session: AsyncSession,
        github_releases_source: Source,
        sample_github_releases_response: list,
        mock_task_instance,
    ):
        """Test complete GitHub releases mode ingestion pipeline."""
        # Mock HTTP client responses for both repositories
        mock_response = AsyncMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value=sample_github_releases_response)
        mock_response.headers = {"ETag": "test-etag-releases"}

        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        # Verify initial state
        count_stmt = select(func.count(ContentItem.id))
        result = await db_session.execute(count_stmt)
        initial_count = result.scalar()
        assert initial_count == 0

        # Mock the HTTP client and Redis in the extractor
        mock_client = AsyncMock()
        mock_client.get_with_response.return_value = mock_response
        mock_client.default_headers = {}
        mock_client.close = AsyncMock()

        from app.core.extractors.github import GitHubExtractor

        with patch.object(GitHubExtractor, "get_http_client", return_value=mock_client):
            with patch("app.core.extractors.github.RedisClient.get_redis", return_value=mock_redis):
                # Run the ingestion task
                result = await _ingest_source_async(mock_task_instance, github_releases_source.name)

        # Verify task result - should get releases from both repositories
        assert result["processed"] == 4  # 2 releases × 2 repositories
        assert result["new"] == 4
        assert result["updated"] == 0
        assert result["errors"] == 0

        # Verify items were created in database
        result = await db_session.execute(count_stmt)
        final_count = result.scalar()
        assert final_count == 4

        # Verify HTTP client was called for both repositories
        assert mock_client.get_with_response.call_count == 2

        # Verify release items content
        items_stmt = select(ContentItem).order_by(ContentItem.external_id)
        result = await db_session.execute(items_stmt)
        items = result.scalars().all()

        assert len(items) == 4

        # Check that all items have the correct release external_id format
        for item in items:
            assert "#release:" in item.external_id
            assert item.source_id == github_releases_source.id

        # Check specific release item
        react_releases = [item for item in items if "facebook/react" in item.external_id]
        assert len(react_releases) == 2

        vscode_releases = [item for item in items if "microsoft/vscode" in item.external_id]
        assert len(vscode_releases) == 2

    async def test_github_ingestion_with_existing_items(
        self,
        db_session: AsyncSession,
        github_search_source: Source,
        sample_github_search_response: dict,
        mock_task_instance,
    ):
        """Test GitHub ingestion with some existing items (updates)."""
        # First, create an existing item
        existing_item = ContentItem(
            source_id=github_search_source.id,
            external_id="123456",
            title="test/awesome-project",
            content="Old description",
            url="https://github.com/test/awesome-project",
            score=1000,  # Different score
            published_at=datetime(2023, 12, 1, 10, 0, 0),
        )
        db_session.add(existing_item)
        await db_session.commit()

        # Mock HTTP response
        mock_response = AsyncMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value=sample_github_search_response)
        mock_response.headers = {"ETag": "test-etag-update"}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        # Run ingestion
        mock_client = AsyncMock()
        mock_client.get_with_response.return_value = mock_response
        mock_client.default_headers = {}
        mock_client.close = AsyncMock()

        from app.core.extractors.github import GitHubExtractor

        with patch.object(GitHubExtractor, "get_http_client", return_value=mock_client):
            with patch("app.core.extractors.github.RedisClient.get_redis", return_value=mock_redis):
                result = await _ingest_source_async(mock_task_instance, github_search_source.name)

        # Verify result shows 1 update and 1 new item
        assert result["processed"] == 2
        assert result["new"] == 1
        assert result["updated"] == 1
        assert result["errors"] == 0

        # Verify the existing item was updated
        updated_item_stmt = select(ContentItem).where(ContentItem.external_id == "123456")
        result = await db_session.execute(updated_item_stmt)
        updated_item = result.scalar_one()

        assert updated_item.content == "An awesome test project for integration testing"
        assert updated_item.score == 1250  # Updated score

    async def test_github_ingestion_with_304_not_modified(
        self,
        db_session: AsyncSession,
        github_search_source: Source,
        mock_task_instance,
    ):
        """Test GitHub ingestion when API returns 304 Not Modified."""
        # Mock HTTP response with 304 status
        mock_response = AsyncMock(spec=Response)
        mock_response.status_code = 304

        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"cached-etag"

        # Run ingestion
        mock_client = AsyncMock()
        mock_client.get_with_response.return_value = mock_response
        mock_client.default_headers = {}
        mock_client.close = AsyncMock()

        from app.core.extractors.github import GitHubExtractor

        with patch.object(GitHubExtractor, "get_http_client", return_value=mock_client):
            with patch("app.core.extractors.github.RedisClient.get_redis", return_value=mock_redis):
                result = await _ingest_source_async(mock_task_instance, github_search_source.name)

        # Should complete successfully with no items processed
        assert result["processed"] == 0
        assert result["new"] == 0
        assert result["updated"] == 0
        assert result["errors"] == 0

        # Verify ingestion run was still created and completed
        runs_stmt = select(IngestionRun).where(IngestionRun.source_id == github_search_source.id)
        result = await db_session.execute(runs_stmt)
        runs = result.scalars().all()

        assert len(runs) == 1
        run = runs[0]
        assert run.status == "completed"
        assert run.items_processed == 0

    async def test_github_ingestion_with_http_error(
        self,
        db_session: AsyncSession,
        github_search_source: Source,
        mock_task_instance,
    ):
        """Test GitHub ingestion handles HTTP errors gracefully."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        # Mock HTTP client to return None (error case)
        mock_client = AsyncMock()
        mock_client.get_with_response.return_value = None  # Simulate HTTP error
        mock_client.default_headers = {}
        mock_client.close = AsyncMock()

        from app.core.extractors.github import GitHubExtractor

        with patch.object(GitHubExtractor, "get_http_client", return_value=mock_client):
            with patch("app.core.extractors.github.RedisClient.get_redis", return_value=mock_redis):
                result = await _ingest_source_async(mock_task_instance, github_search_source.name)

        # Should complete with no items processed
        assert result["processed"] == 0
        assert result["new"] == 0
        assert result["updated"] == 0
        assert result["errors"] == 0

        # Verify ingestion run was created and completed
        runs_stmt = select(IngestionRun).where(IngestionRun.source_id == github_search_source.id)
        result = await db_session.execute(runs_stmt)
        runs = result.scalars().all()

        assert len(runs) == 1
        run = runs[0]
        assert run.status == "completed"

    async def test_github_ingestion_with_normalization_errors(
        self,
        db_session: AsyncSession,
        github_search_source: Source,
        mock_task_instance,
    ):
        """Test GitHub ingestion handles normalization errors gracefully."""
        # Create response with one valid and one invalid item
        response_data = {
            "items": [
                {
                    "id": 123456,
                    "full_name": "test/valid-project",
                    "html_url": "https://github.com/test/valid-project",
                    "description": "A valid project",
                    "stargazers_count": 100,
                    "pushed_at": "2023-12-01T10:00:00Z",
                },
                {
                    # Missing required fields - will cause normalization error
                    "id": 789012,
                    # Missing full_name, html_url, etc.
                },
            ]
        }

        mock_response = AsyncMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value=response_data)
        mock_response.headers = {"ETag": "test-etag-errors"}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        # Run ingestion
        mock_client = AsyncMock()
        mock_client.get_with_response.return_value = mock_response
        mock_client.default_headers = {}
        mock_client.close = AsyncMock()

        from app.core.extractors.github import GitHubExtractor

        with patch.object(GitHubExtractor, "get_http_client", return_value=mock_client):
            with patch("app.core.extractors.github.RedisClient.get_redis", return_value=mock_redis):
                result = await _ingest_source_async(mock_task_instance, github_search_source.name)

        # Should process only the valid item
        assert result["processed"] == 1
        assert result["new"] == 1
        assert result["updated"] == 0
        assert result["errors"] == 1  # One normalization error

        # Verify only one item was created
        count_stmt = select(func.count(ContentItem.id))
        result = await db_session.execute(count_stmt)
        final_count = result.scalar()
        assert final_count == 1

        # Verify ingestion run shows the error
        runs_stmt = select(IngestionRun).where(IngestionRun.source_id == github_search_source.id)
        result = await db_session.execute(runs_stmt)
        runs = result.scalars().all()

        assert len(runs) == 1
        run = runs[0]
        assert run.status == "failed"  # Failed because errors > 0
        assert run.items_processed == 1
        assert run.errors_count == 1

    async def test_github_ingestion_with_since_parameter(
        self,
        db_session: AsyncSession,
        github_search_source: Source,
        sample_github_search_response: dict,
        mock_task_instance,
    ):
        """Test GitHub ingestion respects the since parameter from last ingestion."""
        # Create a completed ingestion run to establish a "since" timestamp
        ingestion_service = IngestionService(db_session)
        completed_time = datetime.now(UTC) - timedelta(hours=1)

        run = await ingestion_service.create_ingestion_run(github_search_source.id)
        await ingestion_service.update_ingestion_run(run.id, status="completed", completed_at=completed_time)

        mock_response = AsyncMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value=sample_github_search_response)
        mock_response.headers = {"ETag": "test-etag-since"}

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        # Run ingestion
        mock_client = AsyncMock()
        mock_client.get_with_response.return_value = mock_response
        mock_client.default_headers = {}
        mock_client.close = AsyncMock()

        from app.core.extractors.github import GitHubExtractor

        with patch.object(GitHubExtractor, "get_http_client", return_value=mock_client):
            with patch("app.core.extractors.github.RedisClient.get_redis", return_value=mock_redis):
                result = await _ingest_source_async(mock_task_instance, github_search_source.name)

        # Verify the HTTP request included a since parameter based on last ingestion
        mock_client.get_with_response.assert_called_once()
        call_args = mock_client.get_with_response.call_args[0][0]

        # The URL should contain a pushed:> query with a timestamp
        assert "pushed:>" in call_args
        assert "search/repositories" in call_args

        # Verify ingestion completed successfully
        assert result["processed"] == 2
        assert result["errors"] == 0

    async def test_github_ingestion_source_not_found(
        self,
        db_session: AsyncSession,
        mock_task_instance,
    ):
        """Test GitHub ingestion handles non-existent source gracefully."""
        # Try to ingest from a source that doesn't exist
        with pytest.raises(ValueError, match="nonexistent_github source not found in database"):
            await _ingest_source_async(mock_task_instance, "nonexistent_github")

    async def test_github_ingestion_inactive_source(
        self,
        db_session: AsyncSession,
        mock_task_instance,
    ):
        """Test GitHub ingestion handles inactive source gracefully."""
        # Create an inactive GitHub source
        import uuid

        unique_name = f"github_inactive_{uuid.uuid4().hex[:8]}"
        inactive_source = Source(
            name=unique_name,
            type="api",
            base_url="https://api.github.com",
            rate_limit=5000,
            config={"token": "test_token", "mode": "search"},
            is_active=False,  # Inactive
        )
        db_session.add(inactive_source)
        await db_session.commit()

        # Try to ingest from inactive source
        with pytest.raises(ValueError, match=f"{unique_name} source not found in database"):
            await _ingest_source_async(mock_task_instance, unique_name)

    async def test_github_releases_with_date_filtering(
        self,
        db_session: AsyncSession,
        github_releases_source: Source,
        mock_task_instance,
    ):
        """Test GitHub releases mode with date filtering."""
        # Create releases with different dates
        old_releases = [
            {
                "id": 111111,
                "name": "Old Release",
                "tag_name": "v1.0.0",
                "html_url": "https://github.com/facebook/react/releases/tag/v1.0.0",
                "body": "Old release",
                "published_at": "2023-11-01T12:00:00Z",  # Old date
            }
        ]

        new_releases = [
            {
                "id": 222222,
                "name": "New Release",
                "tag_name": "v2.0.0",
                "html_url": "https://github.com/facebook/react/releases/tag/v2.0.0",
                "body": "New release",
                "published_at": "2023-12-01T12:00:00Z",  # Recent date
            }
        ]

        # Mock responses to return different data for different calls
        mock_responses = [
            AsyncMock(spec=Response, status_code=200, headers={"ETag": "etag1"}),
            AsyncMock(spec=Response, status_code=200, headers={"ETag": "etag2"}),
        ]
        mock_responses[0].json = AsyncMock(return_value=old_releases + new_releases)
        mock_responses[1].json = AsyncMock(return_value=old_releases + new_releases)

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        # Create a previous ingestion run to establish a "since" date
        ingestion_service = IngestionService(db_session)
        since_time = datetime(2023, 11, 15)  # Between old and new releases

        run = await ingestion_service.create_ingestion_run(github_releases_source.id)
        await ingestion_service.update_ingestion_run(run.id, status="completed", completed_at=since_time)

        # Run ingestion
        mock_client = AsyncMock()
        mock_client.get_with_response.side_effect = mock_responses
        mock_client.default_headers = {}
        mock_client.close = AsyncMock()

        from app.core.extractors.github import GitHubExtractor

        with patch.object(GitHubExtractor, "get_http_client", return_value=mock_client):
            with patch("app.core.extractors.github.RedisClient.get_redis", return_value=mock_redis):
                result = await _ingest_source_async(mock_task_instance, github_releases_source.name)

        # Should only process new releases (after since date) from both repositories
        assert result["processed"] == 2  # 1 new release × 2 repositories
        assert result["new"] == 2
        assert result["updated"] == 0
        assert result["errors"] == 0

        # Verify only new releases were stored
        items_stmt = select(ContentItem).where(ContentItem.source_id == github_releases_source.id)
        result = await db_session.execute(items_stmt)
        items = result.scalars().all()

        assert len(items) == 2
        for item in items:
            assert "New Release" in item.title or "v2.0.0" in item.title
