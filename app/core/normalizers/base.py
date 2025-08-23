import re
from abc import ABC, abstractmethod
from typing import TypeVar

from loguru import logger
from pydantic import BaseModel, ValidationError

from app.core.extractors.base import RawItem
from app.core.registry import register_normalizer
from app.schemas.items import ContentItemCreate

# Type variables for generic normalizer
InputType = TypeVar("InputType", bound=BaseModel)
OutputType = TypeVar("OutputType", bound=BaseModel)


class NormalizationError(Exception):
    """Exception raised when normalization fails."""

    def __init__(self, message: str, item_id: str | None = None, original_error: Exception | None = None) -> None:
        self.message = message
        self.item_id = item_id
        self.original_error = original_error
        super().__init__(self.message)


class BaseNormalizer[InputType: BaseModel, OutputType: BaseModel](ABC):
    """Abstract base class for data normalizers."""

    def __init__(self, source_id: int) -> None:
        self.source_id = source_id

    @abstractmethod
    def normalize(self, raw_item: InputType) -> OutputType:
        """
        Normalize a raw item into the target format.

        Args:
            raw_item: Raw item data to normalize

        Returns:
            Normalized item

        Raises:
            NormalizationError: If normalization fails
        """
        pass

    def normalize_batch(self, raw_items: list[InputType]) -> list[OutputType]:
        """
        Normalize a batch of raw items.

        Args:
            raw_items: List of raw items to normalize

        Returns:
            List of normalized items (excludes failed normalizations)
        """
        normalized_items = []
        failed_count = 0

        for raw_item in raw_items:
            try:
                normalized_item = self.normalize(raw_item)
                normalized_items.append(normalized_item)
            except NormalizationError as e:
                logger.warning(f"Failed to normalize item {e.item_id}: {e.message}")
                failed_count += 1
            except Exception as e:
                logger.error(f"Unexpected error normalizing item: {e}")
                failed_count += 1

        logger.info(f"Normalized {len(normalized_items)} items, {failed_count} failed")
        return normalized_items

    def _clean_text(self, text: str | None) -> str | None:
        """
        Clean and normalize text content.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text or None if input was None/empty
        """
        if not text:
            return None

        # Strip whitespace and normalize line endings
        cleaned = text.strip().replace("\r\n", "\n").replace("\r", "\n")

        # Remove excessive whitespace
        cleaned = re.sub(r"\s+", " ", cleaned)

        return cleaned if cleaned else None

    def _validate_url(self, url: str | None) -> str | None:
        """
        Validate and normalize URL.

        Args:
            url: Raw URL to validate

        Returns:
            Validated URL or None if invalid
        """
        if not url:
            return None

        url = url.strip()

        # Add protocol if missing
        if url and not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Basic URL validation - more permissive pattern
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,}\.?|"  # domain (allow longer TLDs)
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/.*)?$",
            re.IGNORECASE,
        )  # more permissive path matching

        if url_pattern.match(url):
            return url

        logger.warning(f"Invalid URL format: {url}")
        return None


@register_normalizer("default")
class ContentNormalizer(BaseNormalizer[RawItem, ContentItemCreate]):
    """Normalizer for converting RawItem to ContentItemCreate."""

    def normalize(self, raw_item: RawItem) -> ContentItemCreate:
        """
        Normalize a RawItem into ContentItemCreate format.

        Args:
            raw_item: Raw item from extractor

        Returns:
            Normalized ContentItemCreate object

        Raises:
            NormalizationError: If normalization fails
        """
        try:
            # Validate required fields
            if not raw_item.external_id:
                raise NormalizationError("Missing external_id", raw_item.external_id)

            if not raw_item.title:
                raise NormalizationError("Missing title", raw_item.external_id)

            if not raw_item.published_at:
                raise NormalizationError("Missing published_at", raw_item.external_id)

            # Clean and validate data
            title = self._clean_text(raw_item.title)
            if not title:
                raise NormalizationError("Title is empty after cleaning", raw_item.external_id)

            content = self._clean_text(raw_item.content)
            url = self._validate_url(raw_item.url)

            if not url:
                raise NormalizationError("Invalid or missing URL", raw_item.external_id)

            # Validate score (should be non-negative if provided)
            score = raw_item.score
            if score is not None and score < 0:
                logger.warning(f"Negative score {score} for item {raw_item.external_id}, setting to 0")
                score = 0

            return ContentItemCreate(
                source_id=self.source_id,
                external_id=raw_item.external_id,
                title=title,
                content=content,
                url=url,
                score=score,
                published_at=raw_item.published_at,
            )

        except ValidationError as e:
            raise NormalizationError(f"Validation error: {e}", raw_item.external_id, e) from e
        except NormalizationError:
            raise
        except Exception as e:
            raise NormalizationError(f"Unexpected error during normalization: {e}", raw_item.external_id, e) from e
