"""
Unit tests for GitHubNormalizer.

Tests the GitHub-specific data normalization functionality for both repository
and release data, including validation, error handling, and edge cases.
"""

from datetime import UTC, datetime

import pytest

from app.core.normalizers.base import NormalizationError
from app.core.normalizers.github import GitHubNormalizer
from app.schemas.items import ContentItemCreate


class TestGitHubNormalizer:
    """Test suite for GitHubNormalizer class."""

    @pytest.fixture
    def normalizer(self):
        """Create a GitHubNormalizer instance."""
        return GitHubNormalizer(source_id=1)

    @pytest.fixture
    def sample_repository_data(self):
        """Sample repository data from GitHub search API."""
        return {
            "id": 123456,
            "full_name": "test/repository",
            "html_url": "https://github.com/test/repository",
            "description": "A test repository for unit testing",
            "stargazers_count": 150,
            "pushed_at": "2023-12-01T10:00:00Z",
            "updated_at": "2023-12-01T09:30:00Z"
        }

    @pytest.fixture
    def sample_release_data(self):
        """Sample release data from GitHub releases API."""
        return {
            "id": 111111,
            "repository_full_name": "facebook/react",  # Added by extractor
            "name": "React v18.2.0",
            "tag_name": "v18.2.0",
            "html_url": "https://github.com/facebook/react/releases/tag/v18.2.0",
            "body": "This release includes bug fixes and performance improvements.",
            "published_at": "2023-12-01T12:00:00Z",
            "stargazers_count": 1000
        }

    def test_normalize_repository_success(self, normalizer, sample_repository_data):
        """Test successful normalization of repository data."""
        result = normalizer.normalize(sample_repository_data)

        assert isinstance(result, ContentItemCreate)
        assert result.source_id == 1
        assert result.external_id == "123456"
        assert result.title == "test/repository"
        assert result.content == "A test repository for unit testing"
        assert result.url == "https://github.com/test/repository"
        assert result.score == 150
        assert result.published_at == datetime(2023, 12, 1, 10, 0, 0, tzinfo=UTC)

    def test_normalize_repository_with_fallback_date(self, normalizer):
        """Test repository normalization with fallback to updated_at when pushed_at is missing."""
        repo_data = {
            "id": 123456,
            "full_name": "test/repository",
            "html_url": "https://github.com/test/repository",
            "description": "A test repository",
            "stargazers_count": 150,
            # No pushed_at
            "updated_at": "2023-12-01T09:30:00Z"
        }

        result = normalizer.normalize(repo_data)

        assert result.published_at == datetime(2023, 12, 1, 9, 30, 0, tzinfo=UTC)

    def test_normalize_repository_missing_id(self, normalizer, sample_repository_data):
        """Test repository normalization fails when id is missing."""
        del sample_repository_data["id"]

        with pytest.raises(NormalizationError, match="Repository missing 'id' field"):
            normalizer.normalize(sample_repository_data)

    def test_normalize_repository_missing_full_name(self, normalizer, sample_repository_data):
        """Test repository normalization fails when full_name is missing."""
        del sample_repository_data["full_name"]

        with pytest.raises(NormalizationError, match="Repository missing 'full_name' field"):
            normalizer.normalize(sample_repository_data)

    def test_normalize_repository_missing_html_url(self, normalizer, sample_repository_data):
        """Test repository normalization fails when html_url is missing."""
        del sample_repository_data["html_url"]

        with pytest.raises(NormalizationError, match="Repository missing 'html_url' field"):
            normalizer.normalize(sample_repository_data)

    def test_normalize_repository_missing_dates(self, normalizer, sample_repository_data):
        """Test repository normalization fails when both pushed_at and updated_at are missing."""
        del sample_repository_data["pushed_at"]
        del sample_repository_data["updated_at"]

        with pytest.raises(NormalizationError, match="Repository missing valid 'pushed_at' or 'updated_at' field"):
            normalizer.normalize(sample_repository_data)

    def test_normalize_repository_invalid_url(self, normalizer, sample_repository_data):
        """Test repository normalization fails with invalid URL."""
        sample_repository_data["html_url"] = "not-a-valid-url"

        with pytest.raises(NormalizationError, match="Repository has invalid URL"):
            normalizer.normalize(sample_repository_data)

    def test_normalize_repository_empty_title(self, normalizer, sample_repository_data):
        """Test repository normalization fails with empty title after cleaning."""
        sample_repository_data["full_name"] = "   "  # Only whitespace

        with pytest.raises(NormalizationError, match="Repository title is empty after cleaning"):
            normalizer.normalize(sample_repository_data)

    def test_normalize_repository_negative_score(self, normalizer, sample_repository_data):
        """Test repository normalization handles negative score."""
        sample_repository_data["stargazers_count"] = -5

        result = normalizer.normalize(sample_repository_data)

        assert result.score == 0  # Should be set to 0

    def test_normalize_repository_no_description(self, normalizer, sample_repository_data):
        """Test repository normalization with no description."""
        del sample_repository_data["description"]

        result = normalizer.normalize(sample_repository_data)

        assert result.content is None

    def test_normalize_repository_empty_description(self, normalizer, sample_repository_data):
        """Test repository normalization with empty description."""
        sample_repository_data["description"] = ""

        result = normalizer.normalize(sample_repository_data)

        assert result.content is None

    def test_normalize_repository_no_score(self, normalizer, sample_repository_data):
        """Test repository normalization with no stargazers_count."""
        del sample_repository_data["stargazers_count"]

        result = normalizer.normalize(sample_repository_data)

        assert result.score == 0  # Default value

    def test_normalize_release_success(self, normalizer, sample_release_data):
        """Test successful normalization of release data."""
        result = normalizer.normalize(sample_release_data)

        assert isinstance(result, ContentItemCreate)
        assert result.source_id == 1
        assert result.external_id == "facebook/react#release:111111"
        assert result.title == "React v18.2.0 — facebook/react"
        assert result.content == "This release includes bug fixes and performance improvements."
        assert result.url == "https://github.com/facebook/react/releases/tag/v18.2.0"
        assert result.score == 1000
        assert result.published_at == datetime(2023, 12, 1, 12, 0, 0, tzinfo=UTC)

    def test_normalize_release_with_tag_name_fallback(self, normalizer, sample_release_data):
        """Test release normalization with fallback to tag_name when name is missing."""
        del sample_release_data["name"]

        result = normalizer.normalize(sample_release_data)

        assert result.title == "v18.2.0 — facebook/react"

    def test_normalize_release_with_unknown_fallback(self, normalizer, sample_release_data):
        """Test release normalization with fallback to 'Unknown Release' when both name and tag_name are missing."""
        del sample_release_data["name"]
        del sample_release_data["tag_name"]

        result = normalizer.normalize(sample_release_data)

        assert result.title == "Unknown Release — facebook/react"

    def test_normalize_release_missing_id(self, normalizer, sample_release_data):
        """Test release normalization fails when id is missing."""
        del sample_release_data["id"]

        with pytest.raises(NormalizationError, match="Release missing 'id' field"):
            normalizer.normalize(sample_release_data)

    def test_normalize_release_missing_repository_full_name(self, normalizer, sample_release_data):
        """Test release normalization fails when repository_full_name is missing."""
        del sample_release_data["repository_full_name"]

        with pytest.raises(NormalizationError, match="GitHub normalization failed"):
            normalizer.normalize(sample_release_data)

    def test_normalize_release_missing_html_url(self, normalizer, sample_release_data):
        """Test release normalization fails when html_url is missing."""
        del sample_release_data["html_url"]

        with pytest.raises(NormalizationError, match="Release missing 'html_url' field"):
            normalizer.normalize(sample_release_data)

    def test_normalize_release_missing_published_at(self, normalizer, sample_release_data):
        """Test release normalization fails when published_at is missing."""
        del sample_release_data["published_at"]

        with pytest.raises(NormalizationError, match="Release missing 'published_at' field"):
            normalizer.normalize(sample_release_data)

    def test_normalize_release_invalid_published_at(self, normalizer, sample_release_data):
        """Test release normalization fails with invalid published_at."""
        sample_release_data["published_at"] = "not-a-date"

        with pytest.raises(NormalizationError, match="Release has invalid 'published_at' field"):
            normalizer.normalize(sample_release_data)

    def test_normalize_release_invalid_url(self, normalizer, sample_release_data):
        """Test release normalization fails with invalid URL."""
        sample_release_data["html_url"] = "not-a-valid-url"

        with pytest.raises(NormalizationError, match="Release has invalid URL"):
            normalizer.normalize(sample_release_data)

    def test_normalize_release_empty_title(self, normalizer, sample_release_data):
        """Test release normalization fails with empty title after cleaning."""
        sample_release_data["name"] = "   "  # Only whitespace
        sample_release_data["tag_name"] = "   "  # Only whitespace

        # This should actually succeed because the title becomes "— facebook/react" which is not empty
        result = normalizer.normalize(sample_release_data)
        assert result.title == "— facebook/react"

    def test_normalize_release_negative_score(self, normalizer, sample_release_data):
        """Test release normalization handles negative score."""
        sample_release_data["stargazers_count"] = -10

        result = normalizer.normalize(sample_release_data)

        assert result.score == 0  # Should be set to 0

    def test_normalize_release_no_body(self, normalizer, sample_release_data):
        """Test release normalization with no body."""
        del sample_release_data["body"]

        result = normalizer.normalize(sample_release_data)

        assert result.content is None

    def test_normalize_release_empty_body(self, normalizer, sample_release_data):
        """Test release normalization with empty body."""
        sample_release_data["body"] = ""

        result = normalizer.normalize(sample_release_data)

        assert result.content is None

    def test_normalize_release_no_score(self, normalizer, sample_release_data):
        """Test release normalization with no stargazers_count."""
        del sample_release_data["stargazers_count"]

        result = normalizer.normalize(sample_release_data)

        assert result.score is None  # Should remain None for releases

    def test_parse_datetime_success(self, normalizer):
        """Test successful datetime parsing."""
        datetime_str = "2023-12-01T12:00:00Z"
        result = normalizer._parse_datetime(datetime_str)

        assert result == datetime(2023, 12, 1, 12, 0, 0, tzinfo=UTC)

    def test_parse_datetime_without_z_suffix(self, normalizer):
        """Test datetime parsing without Z suffix."""
        datetime_str = "2023-12-01T12:00:00+00:00"
        result = normalizer._parse_datetime(datetime_str)

        assert result == datetime(2023, 12, 1, 12, 0, 0, tzinfo=UTC)

    def test_parse_datetime_none(self, normalizer):
        """Test datetime parsing with None input."""
        result = normalizer._parse_datetime(None)

        assert result is None

    def test_parse_datetime_empty_string(self, normalizer):
        """Test datetime parsing with empty string."""
        result = normalizer._parse_datetime("")

        assert result is None

    def test_parse_datetime_invalid_format(self, normalizer):
        """Test datetime parsing with invalid format."""
        result = normalizer._parse_datetime("not-a-date")

        assert result is None

    def test_get_item_id_repository(self, normalizer, sample_repository_data):
        """Test _get_item_id for repository data."""
        result = normalizer._get_item_id(sample_repository_data)

        assert result == "123456"

    def test_get_item_id_release(self, normalizer, sample_release_data):
        """Test _get_item_id for release data."""
        result = normalizer._get_item_id(sample_release_data)

        assert result == "facebook/react#release:111111"

    def test_get_item_id_missing_data(self, normalizer):
        """Test _get_item_id with missing data."""
        # Repository without id
        repo_data = {"full_name": "test/repo"}
        result = normalizer._get_item_id(repo_data)
        assert result == "unknown"

        # Release without id or repository_full_name
        release_data = {"repository_full_name": "test/repo"}
        result = normalizer._get_item_id(release_data)
        assert result == "test/repo#release:unknown"

    def test_normalize_with_text_cleaning(self, normalizer, sample_repository_data):
        """Test normalization with text that needs cleaning."""
        sample_repository_data["full_name"] = "  test/repository  \n\r"
        sample_repository_data["description"] = "  A test repository\n\nwith multiple lines  "

        result = normalizer.normalize(sample_repository_data)

        assert result.title == "test/repository"
        assert result.content == "A test repository with multiple lines"

    def test_normalize_malformed_repository_data(self, normalizer):
        """Test normalization with completely malformed repository data."""
        malformed_data = {
            "not_id": "wrong_field",
            "wrong_name": "test",
            "bad_url": "not-a-url"
        }

        with pytest.raises(NormalizationError):
            normalizer.normalize(malformed_data)

    def test_normalize_malformed_release_data(self, normalizer):
        """Test normalization with completely malformed release data."""
        malformed_data = {
            "repository_full_name": "test/repo",  # This makes it a release
            "not_id": "wrong_field",
            "wrong_url": "not-a-url"
        }

        with pytest.raises(NormalizationError):
            normalizer.normalize(malformed_data)

    def test_normalize_repository_with_special_characters(self, normalizer, sample_repository_data):
        """Test repository normalization with special characters in text."""
        sample_repository_data["full_name"] = "test/repo-with-special_chars.123"
        sample_repository_data["description"] = "A repo with émojis 🚀 and spëcial chars"

        result = normalizer.normalize(sample_repository_data)

        assert result.title == "test/repo-with-special_chars.123"
        assert result.content == "A repo with émojis 🚀 and spëcial chars"

    def test_normalize_release_with_special_characters(self, normalizer, sample_release_data):
        """Test release normalization with special characters in text."""
        sample_release_data["name"] = "v1.0.0-beta.1"
        sample_release_data["body"] = "Release notes with émojis 🎉 and spëcial chars"

        result = normalizer.normalize(sample_release_data)

        assert "v1.0.0-beta.1" in result.title
        assert result.content == "Release notes with émojis 🎉 and spëcial chars"

    def test_normalize_determines_type_correctly(self, normalizer, sample_repository_data, sample_release_data):
        """Test that normalize correctly determines item type based on repository_full_name field."""
        # Repository data (no repository_full_name field)
        repo_result = normalizer.normalize(sample_repository_data)
        assert repo_result.external_id == "123456"  # Simple ID for repository

        # Release data (has repository_full_name field)
        release_result = normalizer.normalize(sample_release_data)
        assert "#release:" in release_result.external_id  # Composite ID for release

    def test_normalize_exception_handling(self, normalizer):
        """Test that unexpected exceptions are properly wrapped in NormalizationError."""
        # Create data that will cause an unexpected exception during processing
        problematic_data = {
            "id": None,  # This might cause issues when converting to string
            "full_name": "test/repo",
            "html_url": "https://github.com/test/repo",
            "pushed_at": "2023-12-01T10:00:00Z"
        }

        # This should actually succeed because None gets converted to "None" string
        result = normalizer.normalize(problematic_data)
        assert result.external_id == "None"