"""
Unit tests for GitHubExtractor.

Tests the GitHub data extraction functionality including both search and releases modes,
HTTP client mocking, ETag caching, and error handling.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response

from app.core.extractors.base import ExtractorConfig
from app.core.extractors.github import GitHubExtractor
from app.core.http_client import RateLimitedClient
from app.schemas.items import ContentItemCreate

pytestmark = pytest.mark.asyncio


class TestGitHubExtractor:
    """Test suite for GitHubExtractor class."""

    @pytest.fixture
    def search_config(self):
        """Create configuration for search mode."""
        return ExtractorConfig(
            base_url="https://api.github.com",
            rate_limit=5000,
            config={"token": "test_token", "search_endpoint": "/search/repositories", "mode": "search"},
        )

    @pytest.fixture
    def releases_config(self):
        """Create configuration for releases mode."""
        return ExtractorConfig(
            base_url="https://api.github.com",
            rate_limit=5000,
            config={"token": "test_token", "mode": "releases", "repositories": ["facebook/react", "microsoft/vscode"]},
        )

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        client = AsyncMock(spec=RateLimitedClient)
        client.default_headers = {}
        return client

    @pytest.fixture
    def mock_normalizer(self):
        """Create a mock normalizer."""
        normalizer = MagicMock()
        normalizer.normalize.return_value = ContentItemCreate(
            source_id=1,
            external_id="123",
            title="Test Repository",
            content="Test description",
            url="https://github.com/test/repo",
            score=100,
            published_at=datetime.now(UTC),
        )
        return normalizer

    @pytest.fixture
    def sample_repository_data(self):
        """Sample repository data from GitHub search API."""
        return {
            "items": [
                {
                    "id": 123456,
                    "full_name": "test/repository",
                    "html_url": "https://github.com/test/repository",
                    "description": "A test repository",
                    "stargazers_count": 150,
                    "pushed_at": "2023-12-01T10:00:00Z",
                    "updated_at": "2023-12-01T10:00:00Z",
                },
                {
                    "id": 789012,
                    "full_name": "example/project",
                    "html_url": "https://github.com/example/project",
                    "description": "An example project",
                    "stargazers_count": 250,
                    "pushed_at": "2023-12-01T11:00:00Z",
                    "updated_at": "2023-12-01T11:00:00Z",
                },
            ]
        }

    @pytest.fixture
    def sample_release_data(self):
        """Sample release data from GitHub releases API."""
        return [
            {
                "id": 111111,
                "name": "v1.0.0",
                "tag_name": "v1.0.0",
                "html_url": "https://github.com/facebook/react/releases/tag/v1.0.0",
                "body": "Initial release",
                "published_at": "2023-12-01T12:00:00Z",
                "stargazers_count": 1000,
            },
            {
                "id": 222222,
                "name": "v1.1.0",
                "tag_name": "v1.1.0",
                "html_url": "https://github.com/facebook/react/releases/tag/v1.1.0",
                "body": "Bug fixes and improvements",
                "published_at": "2023-12-01T13:00:00Z",
                "stargazers_count": 1000,
            },
        ]

    def test_init_search_mode(self, search_config):
        """Test GitHubExtractor initialization in search mode."""
        extractor = GitHubExtractor(search_config)

        assert extractor.mode == "search"
        assert extractor.repositories is None
        assert extractor.token == "test_token"
        assert extractor.search_endpoint == "/search/repositories"

    def test_init_releases_mode(self, releases_config):
        """Test GitHubExtractor initialization in releases mode."""
        extractor = GitHubExtractor(releases_config)

        assert extractor.mode == "releases"
        assert extractor.repositories == ["facebook/react", "microsoft/vscode"]
        assert extractor.token == "test_token"

    def test_init_releases_mode_missing_repositories(self):
        """Test GitHubExtractor initialization fails when releases mode lacks repositories."""
        config = ExtractorConfig(
            base_url="https://api.github.com",
            rate_limit=5000,
            config={
                "token": "test_token",
                "mode": "releases",
                # Missing repositories
            },
        )

        with pytest.raises(ValueError, match="Releases mode requires 'repositories' list in config"):
            GitHubExtractor(config)

    def test_init_with_normalizer(self, search_config, mock_normalizer):
        """Test GitHubExtractor initialization with normalizer."""
        with patch("app.core.registry.get_normalizer", return_value=mock_normalizer):
            extractor = GitHubExtractor(search_config, source_id=1)
            assert extractor.normalizer == mock_normalizer

    def test_init_without_normalizer(self, search_config):
        """Test GitHubExtractor initialization without normalizer."""
        extractor = GitHubExtractor(search_config)
        assert extractor.normalizer is None

    def test_cache_key_generation(self, search_config, mock_http_client):
        """Test cache key generation for URLs."""
        extractor = GitHubExtractor(search_config, http_client=mock_http_client)

        url1 = "https://api.github.com/search/repositories?q=test"
        url2 = "https://api.github.com/repos/test/repo/releases"

        key1 = extractor._get_cache_key(url1)
        key2 = extractor._get_cache_key(url2)

        assert key1.startswith("github:etag:")
        assert key2.startswith("github:etag:")
        assert key1 != key2  # Different URLs should have different keys

    async def test_fetch_recent_search_mode_success(
        self, search_config, mock_http_client, sample_repository_data, mock_normalizer
    ):
        """Test successful fetch_recent in search mode."""
        # Mock HTTP response
        mock_response = AsyncMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=sample_repository_data)
        mock_response.headers = {"ETag": "test-etag"}
        mock_http_client.get_with_response.return_value = mock_response

        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # No cached ETag
        mock_redis.setex.return_value = True

        with patch("app.core.registry.get_normalizer", return_value=mock_normalizer):
            extractor = GitHubExtractor(search_config, http_client=mock_http_client, source_id=1)

            with patch.object(extractor, "_get_redis_client", return_value=mock_redis):
                since = datetime.now(UTC) - timedelta(hours=1)
                result = await extractor.fetch_recent(since=since, limit=50)

        # Verify results
        assert len(result) == 2  # Two normalized items
        assert all(isinstance(item, ContentItemCreate) for item in result)

        # Verify HTTP client was called correctly
        mock_http_client.get_with_response.assert_called_once()
        call_args = mock_http_client.get_with_response.call_args
        assert "search/repositories" in call_args[0][0]
        assert "per_page=50" in call_args[0][0]

        # Verify normalizer was called for each item
        assert mock_normalizer.normalize.call_count == 2

    async def test_fetch_recent_search_mode_304_not_modified(self, search_config, mock_http_client):
        """Test fetch_recent in search mode with 304 Not Modified response."""
        # Mock HTTP response with 304 status
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 304
        mock_http_client.get_with_response.return_value = mock_response

        # Mock Redis client with cached ETag
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"cached-etag"

        extractor = GitHubExtractor(search_config, http_client=mock_http_client)

        with patch.object(extractor, "_get_redis_client", return_value=mock_redis):
            result = await extractor.fetch_recent()

        # Should return empty list for 304 response
        assert result == []

        # Verify If-None-Match header was sent
        call_args = mock_http_client.get_with_response.call_args
        headers = call_args[1]["headers"]
        assert headers["If-None-Match"] == b"cached-etag"

    async def test_fetch_recent_releases_mode_success(
        self, releases_config, mock_http_client, sample_release_data, mock_normalizer
    ):
        """Test successful fetch_recent in releases mode."""
        # Mock HTTP responses for each repository
        mock_response = AsyncMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=sample_release_data)
        mock_response.headers = {"ETag": "test-etag"}
        mock_http_client.get_with_response.return_value = mock_response

        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        with patch("app.core.registry.get_normalizer", return_value=mock_normalizer):
            extractor = GitHubExtractor(releases_config, http_client=mock_http_client, source_id=1)

            with patch.object(extractor, "_get_redis_client", return_value=mock_redis):
                result = await extractor.fetch_recent(limit=10)

        # Should get releases from both repositories
        assert len(result) == 4  # 2 releases × 2 repositories
        assert all(isinstance(item, ContentItemCreate) for item in result)

        # Verify HTTP client was called for each repository
        assert mock_http_client.get_with_response.call_count == 2

        # Verify normalizer was called for each release
        assert mock_normalizer.normalize.call_count == 4

    async def test_fetch_recent_releases_mode_304_not_modified(self, releases_config, mock_http_client):
        """Test fetch_recent in releases mode with 304 Not Modified response."""
        # Mock HTTP response with 304 status
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 304
        mock_http_client.get_with_response.return_value = mock_response

        # Mock Redis client with cached ETag
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"cached-etag"

        extractor = GitHubExtractor(releases_config, http_client=mock_http_client)

        with patch.object(extractor, "_get_redis_client", return_value=mock_redis):
            result = await extractor.fetch_recent()

        # Should return empty list when all repositories return 304
        assert result == []

        # Should have called each repository
        assert mock_http_client.get_with_response.call_count == 2

    async def test_fetch_recent_releases_mode_with_since_filter(
        self, releases_config, mock_http_client, mock_normalizer
    ):
        """Test fetch_recent in releases mode with since date filtering."""
        # Create release data with different dates
        old_release = {
            "id": 111111,
            "name": "v1.0.0",
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/facebook/react/releases/tag/v1.0.0",
            "body": "Old release",
            "published_at": "2023-11-01T12:00:00Z",  # Old date
        }
        new_release = {
            "id": 222222,
            "name": "v1.1.0",
            "tag_name": "v1.1.0",
            "html_url": "https://github.com/facebook/react/releases/tag/v1.1.0",
            "body": "New release",
            "published_at": "2023-12-01T12:00:00Z",  # Recent date
        }

        mock_response = AsyncMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=[old_release, new_release])
        mock_response.headers = {"ETag": "test-etag"}
        mock_http_client.get_with_response.return_value = mock_response

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        with patch("app.core.registry.get_normalizer", return_value=mock_normalizer):
            extractor = GitHubExtractor(releases_config, http_client=mock_http_client, source_id=1)

            with patch.object(extractor, "_get_redis_client", return_value=mock_redis):
                # Filter to only get releases after November 15, 2023
                since = datetime(2023, 11, 15, tzinfo=UTC)
                result = await extractor.fetch_recent(since=since)

        # Should only get the new release from each repository (2 total)
        assert len(result) == 2

        # Verify normalizer was called only for new releases
        assert mock_normalizer.normalize.call_count == 2

    async def test_fetch_recent_http_error(self, search_config, mock_http_client):
        """Test fetch_recent handles HTTP errors gracefully."""
        # Mock HTTP client to return None (error case)
        mock_http_client.get_with_response.return_value = None

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        extractor = GitHubExtractor(search_config, http_client=mock_http_client)

        with patch.object(extractor, "_get_redis_client", return_value=mock_redis):
            result = await extractor.fetch_recent()

        # Should return empty list on HTTP error
        assert result == []

    async def test_fetch_recent_json_parse_error(self, search_config, mock_http_client):
        """Test fetch_recent handles JSON parsing errors."""
        # Mock HTTP response with invalid JSON
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.headers = {}
        mock_http_client.get_with_response.return_value = mock_response

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        extractor = GitHubExtractor(search_config, http_client=mock_http_client)

        with patch.object(extractor, "_get_redis_client", return_value=mock_redis):
            result = await extractor.fetch_recent()

        # Should return empty list on JSON error
        assert result == []

    async def test_fetch_recent_normalization_error(self, search_config, mock_http_client, sample_repository_data):
        """Test fetch_recent handles normalization errors gracefully."""
        # Mock HTTP response
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_repository_data
        mock_response.headers = {}
        mock_http_client.get_with_response.return_value = mock_response

        # Mock normalizer that raises exceptions
        mock_normalizer = MagicMock()
        mock_normalizer.normalize.side_effect = Exception("Normalization failed")

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch("app.core.registry.get_normalizer", return_value=mock_normalizer):
            extractor = GitHubExtractor(search_config, http_client=mock_http_client, source_id=1)

            with patch.object(extractor, "_get_redis_client", return_value=mock_redis):
                result = await extractor.fetch_recent()

        # Should return empty list when all normalizations fail
        assert result == []

    async def test_fetch_recent_redis_error(
        self, search_config, mock_http_client, sample_repository_data, mock_normalizer
    ):
        """Test fetch_recent handles Redis errors gracefully."""
        # Mock HTTP response
        mock_response = AsyncMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=sample_repository_data)
        mock_response.headers = {"ETag": "test-etag"}
        mock_http_client.get_with_response.return_value = mock_response

        # Mock Redis client that raises exceptions
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")
        mock_redis.setex.side_effect = Exception("Redis error")

        with patch("app.core.registry.get_normalizer", return_value=mock_normalizer):
            extractor = GitHubExtractor(search_config, http_client=mock_http_client, source_id=1)

            with patch.object(extractor, "_get_redis_client", return_value=mock_redis):
                result = await extractor.fetch_recent()

        # Should still work despite Redis errors
        assert len(result) == 2

    async def test_fetch_batch(self, search_config, mock_http_client, sample_repository_data, mock_normalizer):
        """Test fetch_batch method."""
        # Mock HTTP response
        mock_response = AsyncMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=sample_repository_data)
        mock_response.headers = {}
        mock_http_client.get_with_response.return_value = mock_response

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch("app.core.registry.get_normalizer", return_value=mock_normalizer):
            extractor = GitHubExtractor(search_config, http_client=mock_http_client, source_id=1)

            with patch.object(extractor, "_get_redis_client", return_value=mock_redis):
                result = await extractor.fetch_batch(limit=25)

        # Should delegate to fetch_recent
        assert len(result) == 2

        # Verify limit was passed through
        call_args = mock_http_client.get_with_response.call_args
        assert "per_page=25" in call_args[0][0]

    async def test_health_check_success(self, search_config, mock_http_client):
        """Test successful health check."""
        # Mock successful rate limit response
        mock_http_client.get_json.return_value = {"rate": {"limit": 5000, "remaining": 4999, "reset": 1234567890}}

        extractor = GitHubExtractor(search_config, http_client=mock_http_client)
        result = await extractor.health_check()

        assert result is True
        mock_http_client.get_json.assert_called_once_with(
            "https://api.github.com/rate_limit",
            headers={"Accept": "application/vnd.github.v3+json", "Authorization": "Bearer test_token"},
        )

    async def test_health_check_failure(self, search_config, mock_http_client):
        """Test health check failure."""
        # Mock failed response
        mock_http_client.get_json.return_value = None

        extractor = GitHubExtractor(search_config, http_client=mock_http_client)
        result = await extractor.health_check()

        assert result is False

    async def test_health_check_exception(self, search_config, mock_http_client):
        """Test health check handles exceptions."""
        # Mock exception
        mock_http_client.get_json.side_effect = Exception("Network error")

        extractor = GitHubExtractor(search_config, http_client=mock_http_client)
        result = await extractor.health_check()

        assert result is False

    async def test_close(self, search_config, mock_http_client):
        """Test close method."""
        extractor = GitHubExtractor(search_config, http_client=mock_http_client)
        await extractor.close()

        mock_http_client.close.assert_called_once()

    async def test_async_context_manager(self, search_config, mock_http_client):
        """Test async context manager functionality."""
        async with GitHubExtractor(search_config, http_client=mock_http_client) as extractor:
            assert isinstance(extractor, GitHubExtractor)

        # Should have called close
        mock_http_client.close.assert_called_once()

    async def test_unknown_mode(self, mock_http_client):
        """Test extractor with unknown mode."""
        config = ExtractorConfig(
            base_url="https://api.github.com", rate_limit=5000, config={"token": "test_token", "mode": "unknown_mode"}
        )

        extractor = GitHubExtractor(config, http_client=mock_http_client)

        # Should handle unknown mode gracefully
        result = await extractor.fetch_recent()
        assert result == []
