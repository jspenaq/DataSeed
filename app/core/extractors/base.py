from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel


class RawItem(BaseModel):
    """Raw item data from external sources before normalization."""

    external_id: str
    title: str
    content: str | None = None
    url: str
    score: int | None = None
    published_at: datetime
    raw_data: dict[str, Any]  # Store original response for debugging


class ExtractorConfig(BaseModel):
    """Configuration for extractors."""

    base_url: str
    rate_limit: int
    config: dict[str, Any]


class BaseExtractor(ABC):
    """Abstract base class for all data extractors."""

    def __init__(self, config: ExtractorConfig):
        self.config = config
        self.base_url = config.base_url
        self.rate_limit = config.rate_limit
        self.extractor_config = config.config

    @abstractmethod
    async def fetch_recent(self, since: datetime | None = None, limit: int = 100) -> list[RawItem]:
        """
        Fetch recent items from the source.

        Args:
            since: Only fetch items published after this datetime
            limit: Maximum number of items to fetch

        Returns:
            List of raw items from the source
        """
        pass

    @abstractmethod
    async def fetch_batch(self, limit: int = 100) -> list[RawItem]:
        """
        Fetch a batch of items from the source.

        Args:
            limit: Maximum number of items to fetch

        Returns:
            List of raw items from the source
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the extractor can connect to the source.

        Returns:
            True if the source is accessible, False otherwise
        """
        pass


class ExtractorProtocol(Protocol):
    """Protocol for type checking extractors."""

    async def fetch_recent(self, since: datetime | None = None, limit: int = 100) -> list[RawItem]: ...

    async def fetch_batch(self, limit: int = 100) -> list[RawItem]: ...

    async def health_check(self) -> bool: ...
