from typing import Any

from loguru import logger

from app.core.extractors.base import RawItem
from app.core.normalizers.base import ContentNormalizer, NormalizationError
from app.core.registry import register_normalizer
from app.schemas.items import ContentItemCreate


@register_normalizer("hackernews")
class HackerNewsNormalizer(ContentNormalizer):
    """HackerNews-specific normalizer with custom field mapping and validation."""

    def normalize(self, raw_item: RawItem) -> ContentItemCreate:
        """
        Normalize a HackerNews RawItem with HN-specific logic.

        Args:
            raw_item: Raw item from HackerNews extractor

        Returns:
            Normalized ContentItemCreate object

        Raises:
            NormalizationError: If normalization fails
        """
        try:
            # Call parent normalization first
            normalized_item = super().normalize(raw_item)

            # Apply HackerNews-specific transformations
            normalized_item = self._apply_hackernews_transformations(normalized_item, raw_item)

            return normalized_item

        except NormalizationError:
            raise
        except Exception as e:
            raise NormalizationError(f"HackerNews normalization failed: {e}", raw_item.external_id, e)

    def _apply_hackernews_transformations(
        self,
        normalized_item: ContentItemCreate,
        raw_item: RawItem,
    ) -> ContentItemCreate:
        """
        Apply HackerNews-specific transformations to the normalized item.

        Args:
            normalized_item: Base normalized item
            raw_item: Original raw item for reference

        Returns:
            Transformed ContentItemCreate object
        """
        # Get raw data for HN-specific fields
        raw_data = raw_item.raw_data

        # Handle HackerNews URL logic
        url = self._normalize_hackernews_url(normalized_item.url, raw_data)

        # Handle HackerNews content (text field)
        content = self._normalize_hackernews_content(normalized_item.content, raw_data)

        # Handle HackerNews score (ensure it's reasonable)
        score = self._normalize_hackernews_score(normalized_item.score, raw_data)

        # Create new normalized item with HN-specific transformations
        return ContentItemCreate(
            source_id=normalized_item.source_id,
            external_id=normalized_item.external_id,
            title=normalized_item.title,
            content=content,
            url=url,
            score=score,
            published_at=normalized_item.published_at,
        )

    def _normalize_hackernews_url(self, url: str, raw_data: dict[str, Any]) -> str:
        """
        Normalize HackerNews URL with HN-specific logic.

        Args:
            url: Base normalized URL
            raw_data: Original HN API response

        Returns:
            HN-specific normalized URL
        """
        # If no external URL, use HN discussion URL
        if not raw_data.get("url"):
            hn_id = raw_data.get("id")
            if hn_id:
                return f"https://news.ycombinator.com/item?id={hn_id}"

        # For Ask HN, Show HN, etc., prefer HN discussion URL
        title = raw_data.get("title", "").lower()
        if any(prefix in title for prefix in ["ask hn", "show hn", "tell hn"]):
            hn_id = raw_data.get("id")
            if hn_id:
                return f"https://news.ycombinator.com/item?id={hn_id}"

        return url

    def _normalize_hackernews_content(self, content: str | None, raw_data: dict[str, Any]) -> str | None:
        """
        Normalize HackerNews content with HN-specific logic.

        Args:
            content: Base normalized content
            raw_data: Original HN API response

        Returns:
            HN-specific normalized content
        """
        # HackerNews HTML content needs special handling
        if content:
            # Convert HN's HTML entities and formatting
            content = self._clean_hackernews_html(content)

        # For stories without text, try to extract from title context
        if not content:
            title = raw_data.get("title", "")
            if any(prefix in title.lower() for prefix in ["ask hn:", "show hn:", "tell hn:"]):
                # Extract the question/description part after the prefix
                for prefix in ["Ask HN:", "Show HN:", "Tell HN:"]:
                    if title.startswith(prefix):
                        content = title[len(prefix) :].strip()
                        break

        return content

    def _normalize_hackernews_score(self, score: int | None, raw_data: dict[str, Any]) -> int | None:
        """
        Normalize HackerNews score with HN-specific validation.

        Args:
            score: Base normalized score
            raw_data: Original HN API response

        Returns:
            HN-specific normalized score
        """
        # HackerNews scores should be reasonable (0-10000 typically)
        if score is not None:
            if score > 10000:
                logger.warning(f"Unusually high HN score {score} for item {raw_data.get('id')}")
            elif score < 0:
                logger.warning(f"Negative HN score {score} for item {raw_data.get('id')}, setting to 0")
                score = 0

        return score

    def _clean_hackernews_html(self, content: str) -> str:
        """
        Clean HackerNews HTML content.

        Args:
            content: Raw HTML content from HN

        Returns:
            Cleaned text content
        """
        import html
        import re

        # Decode HTML entities
        content = html.unescape(content)

        # Convert HN-specific formatting
        # <p> tags become double newlines
        content = re.sub(r"<p>", "\n\n", content)
        content = re.sub(r"</p>", "", content)

        # <i> tags for italics
        content = re.sub(r"<i>(.*?)</i>", r"*\1*", content)

        # Links
        content = re.sub(r'<a href="([^"]*)"[^>]*>(.*?)</a>', r"\2 (\1)", content)

        # Remove any remaining HTML tags
        content = re.sub(r"<[^>]+>", "", content)

        # Clean up excessive whitespace
        content = re.sub(r"\n\s*\n\s*\n", "\n\n", content)
        content = re.sub(r"[ \t]+", " ", content)

        return content.strip()


@register_normalizer("generic")
class GenericContentNormalizer(ContentNormalizer):
    """Generic content normalizer for sources without specific requirements."""

    def normalize(self, raw_item: RawItem) -> ContentItemCreate:
        """
        Normalize a generic RawItem using base normalization only.

        Args:
            raw_item: Raw item from any extractor

        Returns:
            Normalized ContentItemCreate object
        """
        return super().normalize(raw_item)


@register_normalizer("reddit")
class RedditNormalizer(ContentNormalizer):
    """Reddit-specific normalizer with custom field mapping and validation."""

    def normalize(self, raw_item: RawItem) -> ContentItemCreate:
        """
        Normalize a Reddit RawItem with Reddit-specific logic.

        Args:
            raw_item: Raw item from Reddit extractor

        Returns:
            Normalized ContentItemCreate object

        Raises:
            NormalizationError: If normalization fails
        """
        try:
            # Call parent normalization first
            normalized_item = super().normalize(raw_item)

            # Apply Reddit-specific transformations
            normalized_item = self._apply_reddit_transformations(normalized_item, raw_item)

            return normalized_item

        except NormalizationError:
            raise
        except Exception as e:
            raise NormalizationError(f"Reddit normalization failed: {e}", raw_item.external_id, e)

    def _apply_reddit_transformations(
        self,
        normalized_item: ContentItemCreate,
        raw_item: RawItem,
    ) -> ContentItemCreate:
        """
        Apply Reddit-specific transformations to the normalized item.

        Args:
            normalized_item: Base normalized item
            raw_item: Original raw item for reference

        Returns:
            Transformed ContentItemCreate object
        """
        raw_data = raw_item.raw_data

        # Handle Reddit URL logic (prefer permalink for discussions)
        url = self._normalize_reddit_url(normalized_item.url, raw_data)

        # Handle Reddit content (selftext field)
        content = self._normalize_reddit_content(normalized_item.content, raw_data)

        # Handle Reddit score (upvotes)
        score = self._normalize_reddit_score(normalized_item.score, raw_data)

        return ContentItemCreate(
            source_id=normalized_item.source_id,
            external_id=normalized_item.external_id,
            title=normalized_item.title,
            content=content,
            url=url,
            score=score,
            published_at=normalized_item.published_at,
        )

    def _normalize_reddit_url(self, url: str, raw_data: dict[str, Any]) -> str:
        """Normalize Reddit URL, preferring Reddit permalink for discussions."""
        # For self posts, use Reddit permalink
        if raw_data.get("is_self"):
            permalink = raw_data.get("permalink")
            if permalink:
                return f"https://reddit.com{permalink}"
        return url

    def _normalize_reddit_content(self, content: str | None, raw_data: dict[str, Any]) -> str | None:
        """Normalize Reddit content from selftext field."""
        # Reddit uses 'selftext' for post content
        selftext = raw_data.get("selftext")
        if selftext and selftext.strip():
            return selftext.strip()
        return content

    def _normalize_reddit_score(self, score: int | None, raw_data: dict[str, Any]) -> int | None:
        """Normalize Reddit score (upvotes)."""
        # Reddit scores can be negative, which is normal
        return score


@register_normalizer("producthunt")
class ProductHuntNormalizer(ContentNormalizer):
    """ProductHunt-specific normalizer with custom field mapping and validation."""

    def normalize(self, raw_item: RawItem) -> ContentItemCreate:
        """
        Normalize a ProductHunt RawItem with ProductHunt-specific logic.

        Args:
            raw_item: Raw item from ProductHunt extractor

        Returns:
            Normalized ContentItemCreate object

        Raises:
            NormalizationError: If normalization fails
        """
        try:
            # Call parent normalization first
            normalized_item = super().normalize(raw_item)

            # Apply ProductHunt-specific transformations
            normalized_item = self._apply_producthunt_transformations(normalized_item, raw_item)

            return normalized_item

        except NormalizationError:
            raise
        except Exception as e:
            raise NormalizationError(f"ProductHunt normalization failed: {e}", raw_item.external_id, e)

    def _apply_producthunt_transformations(
        self,
        normalized_item: ContentItemCreate,
        raw_item: RawItem,
    ) -> ContentItemCreate:
        """
        Apply ProductHunt-specific transformations to the normalized item.

        Args:
            normalized_item: Base normalized item
            raw_item: Original raw item for reference

        Returns:
            Transformed ContentItemCreate object
        """
        raw_data = raw_item.raw_data

        # Handle ProductHunt content (tagline field)
        content = self._normalize_producthunt_content(normalized_item.content, raw_data)

        # Handle ProductHunt score (votes_count)
        score = self._normalize_producthunt_score(normalized_item.score, raw_data)

        return ContentItemCreate(
            source_id=normalized_item.source_id,
            external_id=normalized_item.external_id,
            title=normalized_item.title,
            content=content,
            url=normalized_item.url,
            score=score,
            published_at=normalized_item.published_at,
        )

    def _normalize_producthunt_content(self, content: str | None, raw_data: dict[str, Any]) -> str | None:
        """Normalize ProductHunt content from tagline field."""
        # ProductHunt uses 'tagline' for product description
        tagline = raw_data.get("tagline")
        if tagline and tagline.strip():
            return tagline.strip()
        return content

    def _normalize_producthunt_score(self, score: int | None, raw_data: dict[str, Any]) -> int | None:
        """Normalize ProductHunt score (votes_count)."""
        # ProductHunt votes should be non-negative
        if score is not None and score < 0:
            logger.warning(f"Negative ProductHunt votes {score} for product {raw_data.get('name')}, setting to 0")
            score = 0
        return score
