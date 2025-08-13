from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel

from app.core.http_client import RateLimitedClient


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

    def get_http_client(self) -> RateLimitedClient:
        """
        Create HTTP client with configuration from source config.

        Returns:
            Configured RateLimitedClient instance
        """
        client_config = self.extractor_config.get("client", {})
        return RateLimitedClient(
            rate_limit=self.rate_limit,
            retries=client_config.get("retries", 3),
            semaphore_size=client_config.get("semaphore_size", 10),
            timeout=client_config.get("timeout", 10.0),
        )

    async def close(self):
        """Close any resources used by the extractor."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

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
