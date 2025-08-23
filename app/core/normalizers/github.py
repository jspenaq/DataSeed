"""
GitHub-specific normalizer for transforming raw GitHub data into ContentItem schema.

This module handles normalization of both repository search results and release data
from the GitHub API, transforming them into the standardized ContentItem format.
"""

from datetime import datetime
from typing import Any

from loguru import logger

from app.core.normalizers.base import BaseNormalizer, NormalizationError
from app.core.registry import register_normalizer
from app.schemas.items import ContentItemCreate


@register_normalizer("github")
class GitHubNormalizer(BaseNormalizer):
    """
    GitHub-specific normalizer for repositories and releases.

    Handles two types of GitHub data:
    - Repository search results (from search API)
    - Release data (from releases API)
    """

    def normalize(self, raw_item: dict[str, Any]) -> ContentItemCreate:
        """
        Normalize a raw GitHub item into ContentItemCreate format.

        Determines whether the item is a repository or release based on the presence
        of the 'repository_full_name' field, then applies appropriate normalization.

        Args:
            raw_item: Raw data dictionary from GitHub API

        Returns:
            Normalized ContentItemCreate object

        Raises:
            NormalizationError: If normalization fails
        """
        try:
            # Determine item type based on presence of repository_full_name field
            if "repository_full_name" in raw_item:
                return self._normalize_release(raw_item)
            return self._normalize_repository(raw_item)

        except KeyError as e:
            raise NormalizationError(f"Missing required field: {e}", self._get_item_id(raw_item)) from e
        except Exception as e:
            raise NormalizationError(f"GitHub normalization failed: {e}", self._get_item_id(raw_item)) from e

    def _normalize_repository(self, repo: dict[str, Any]) -> ContentItemCreate:
        """
        Normalize a GitHub repository item.

        Args:
            repo: Raw repository data from GitHub search API

        Returns:
            Normalized ContentItemCreate object
        """
        # Validate required fields
        if "id" not in repo:
            raise NormalizationError("Repository missing 'id' field")
        if "full_name" not in repo:
            raise NormalizationError("Repository missing 'full_name' field")
        if "html_url" not in repo:
            raise NormalizationError("Repository missing 'html_url' field")

        # Extract and validate published_at with fallback
        published_at = self._parse_datetime(repo.get("pushed_at") or repo.get("updated_at"))
        if not published_at:
            raise NormalizationError("Repository missing valid 'pushed_at' or 'updated_at' field")

        # Clean and validate data
        external_id = str(repo["id"])
        title = self._clean_text(repo["full_name"])
        content = self._clean_text(repo.get("description"))
        url = self._validate_url(repo["html_url"])
        score = repo.get("stargazers_count", 0)

        if not title:
            raise NormalizationError("Repository title is empty after cleaning")
        if not url:
            raise NormalizationError("Repository has invalid URL")

        # Ensure score is non-negative
        if score is not None and score < 0:
            logger.warning(f"Negative GitHub stars {score} for repo {repo.get('full_name')}, setting to 0")
            score = 0

        return ContentItemCreate(
            source_id=self.source_id,
            external_id=external_id,
            title=title,
            content=content,
            url=url,
            score=score,
            published_at=published_at,
        )

    def _normalize_release(self, release: dict[str, Any]) -> ContentItemCreate:
        """
        Normalize a GitHub release item.

        Args:
            release: Raw release data from GitHub releases API

        Returns:
            Normalized ContentItemCreate object
        """
        # Validate required fields
        if "id" not in release:
            raise NormalizationError("Release missing 'id' field")
        if "repository_full_name" not in release:
            raise NormalizationError("Release missing 'repository_full_name' field")
        if "html_url" not in release:
            raise NormalizationError("Release missing 'html_url' field")
        if "published_at" not in release:
            raise NormalizationError("Release missing 'published_at' field")

        # Extract and validate published_at
        published_at = self._parse_datetime(release["published_at"])
        if not published_at:
            raise NormalizationError("Release has invalid 'published_at' field")

        # Build external_id and title
        repo_name = release["repository_full_name"]
        release_id = release["id"]
        external_id = f"{repo_name}#release:{release_id}"

        # Create title from release name/tag and repository
        release_name = release.get("name") or release.get("tag_name", "Unknown Release")
        title = f"{release_name} — {repo_name}"

        # Clean and validate data
        title = self._clean_text(title)
        content = self._clean_text(release.get("body"))
        url = self._validate_url(release["html_url"])
        score = release.get("stargazers_count")  # May not be present for releases

        if not title:
            raise NormalizationError("Release title is empty after cleaning")
        if not url:
            raise NormalizationError("Release has invalid URL")

        # Ensure score is non-negative if present
        if score is not None and score < 0:
            logger.warning(f"Negative GitHub stars {score} for release {external_id}, setting to 0")
            score = 0

        return ContentItemCreate(
            source_id=self.source_id,
            external_id=external_id,
            title=title,
            content=content,
            url=url,
            score=score,
            published_at=published_at,
        )

    def _parse_datetime(self, datetime_str: str | None) -> datetime | None:
        """
        Parse GitHub datetime string into datetime object.

        Args:
            datetime_str: ISO format datetime string from GitHub API

        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not datetime_str:
            return None

        try:
            # GitHub API returns ISO format with 'Z' suffix
            if datetime_str.endswith("Z"):
                datetime_str = datetime_str[:-1] + "+00:00"
            return datetime.fromisoformat(datetime_str)
        except ValueError as e:
            logger.warning(f"Could not parse datetime: {datetime_str} - {e}")
            return None

    def _get_item_id(self, raw_item: dict[str, Any]) -> str | None:
        """
        Extract item ID for error reporting.

        Args:
            raw_item: Raw item data

        Returns:
            Item ID string or None if not found
        """
        if "repository_full_name" in raw_item:
            # Release item
            repo_name = raw_item.get("repository_full_name", "unknown")
            release_id = raw_item.get("id", "unknown")
            return f"{repo_name}#release:{release_id}"
        # Repository item
        return str(raw_item.get("id", "unknown"))
