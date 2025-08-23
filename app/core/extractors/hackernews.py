import asyncio
from datetime import UTC, datetime
from typing import Any, cast

from loguru import logger

from app.core.extractors.base import BaseExtractor, ExtractorConfig, RawItem
from app.core.http_client import RateLimitedClient
from app.core.registry import register_extractor


@register_extractor("hackernews")
class HackerNewsExtractor(BaseExtractor):
    """HackerNews API extractor using httpx for async operations."""

    def __init__(self, config: ExtractorConfig, source_id: int, http_client: RateLimitedClient | None = None) -> None:
        super().__init__(config, source_id)
        self.http_client = http_client or self.get_http_client()
        # Add user agent to the client if not provided
        if http_client is None:
            self.http_client.default_headers["User-Agent"] = "DataSeed/1.0 (https://github.com/jspenaq/dataseed)"
        self.items_endpoint = self.extractor_config.get("items_endpoint", "/topstories.json")
        self.detail_endpoint = self.extractor_config.get("detail_endpoint", "/item/{id}.json")

    async def _make_request(self, url: str, retries: int = 3) -> dict[str, Any] | list[Any] | None:
        """
        Make HTTP request with retry logic and rate limiting.

        Args:
            url: URL to request
            retries: Number of retry attempts

        Returns:
            JSON response data or None if failed
        """
        return await self.http_client.get_json(url, retries=retries)

    async def _fetch_story_ids(self, limit: int = 100) -> list[int]:
        """
        Fetch top story IDs from HackerNews.

        Args:
            limit: Maximum number of story IDs to fetch

        Returns:
            List of story IDs
        """
        url = self.base_url + self.items_endpoint
        logger.info(f"Fetching top story IDs from {url}")

        data = await self._make_request(url)
        if data is None:
            logger.error("Failed to fetch story IDs")
            return []

        if not isinstance(data, list):
            logger.error(f"Expected list of story IDs, got {type(data)}")
            return []

        # Cast to List[Any] to satisfy type checker, then process
        story_list = cast("list[Any]", data)
        limited_data = story_list[:limit]
        story_ids = [int(item_id) for item_id in limited_data if isinstance(item_id, int | str)]
        logger.info(f"Retrieved {len(story_ids)} story IDs")
        return story_ids

    async def _fetch_item_details(self, item_id: int) -> dict[str, Any] | None:
        """
        Fetch details for a specific item ID.

        Args:
            item_id: HackerNews item ID

        Returns:
            Item details or None if failed
        """
        url = self.base_url + self.detail_endpoint.format(id=item_id)
        result = await self._make_request(url)
        # Ensure we return a dict for item details
        return result if isinstance(result, dict) else None

    def _parse_item(self, item_data: dict[str, Any]) -> RawItem | None:
        """
        Parse HackerNews item data into RawItem format.

        Args:
            item_data: Raw item data from HN API

        Returns:
            Parsed RawItem or None if invalid
        """
        try:
            # Skip deleted or invalid items
            if item_data.get("deleted") or item_data.get("dead"):
                return None

            # Only process stories (not comments, jobs, etc.)
            if item_data.get("type") != "story":
                return None

            # Required fields
            item_id = item_data.get("id")
            title = item_data.get("title")
            timestamp = item_data.get("time")

            if not all([item_id, title, timestamp]):
                logger.warning(f"Missing required fields in item {item_id}")
                return None

            # Ensure types are correct
            if not isinstance(title, str):
                logger.warning(f"Title is not a string for item {item_id}")
                return None

            if not isinstance(timestamp, int | float):
                logger.warning(f"Timestamp is not a number for item {item_id}")
                return None

            # Convert timestamp to datetime
            published_at = datetime.fromtimestamp(float(timestamp), tz=UTC)

            # Get URL (prefer actual URL over HN discussion URL)
            url = item_data.get("url")
            if not url:
                url = f"https://news.ycombinator.com/item?id={item_id}"

            return RawItem(
                external_id=str(item_id),
                title=title,
                content=item_data.get("text"),  # Story text if available
                url=url,
                score=item_data.get("score", 0),
                published_at=published_at,
                raw_data=item_data,
            )

        except Exception as e:
            logger.error(f"Error parsing item {item_data.get('id', 'unknown')}: {e}")
            return None

    async def fetch_recent(self, since: datetime | None = None, limit: int = 100) -> list[RawItem]:
        """
        Fetch recent items from HackerNews.

        Args:
            since: Only fetch items published after this datetime
            limit: Maximum number of items to fetch

        Returns:
            List of raw items from HackerNews
        """
        logger.info(f"Fetching recent HackerNews items (limit: {limit}, since: {since})")

        # Get story IDs
        story_ids = await self._fetch_story_ids(limit * 2)  # Fetch more IDs to account for filtering
        if not story_ids:
            return []

        # Fetch item details concurrently with semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests

        async def fetch_with_semaphore(item_id: int) -> RawItem | None:
            async with semaphore:
                item_data = await self._fetch_item_details(item_id)
                if item_data:
                    return self._parse_item(item_data)
                return None

        # Create tasks for all story IDs
        tasks = [fetch_with_semaphore(story_id) for story_id in story_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None results and exceptions
        items = []
        for result in results:
            if isinstance(result, RawItem):
                # Apply time filter if specified
                if since is None or result.published_at > since:
                    items.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Error fetching item: {result}")

        # Sort by published date (newest first) and apply limit
        items.sort(key=lambda x: x.published_at, reverse=True)
        items = items[:limit]

        logger.info(f"Successfully fetched {len(items)} HackerNews items")
        return items

    async def fetch_batch(self, limit: int = 100) -> list[RawItem]:
        """
        Fetch a batch of items from HackerNews.

        Args:
            limit: Maximum number of items to fetch

        Returns:
            List of raw items from HackerNews
        """
        return await self.fetch_recent(limit=limit)

    async def health_check(self) -> bool:
        """
        Check if HackerNews API is accessible.

        Returns:
            True if API is accessible, False otherwise
        """
        try:
            url = self.base_url + self.items_endpoint
            data = await self._make_request(url)
            return data is not None and isinstance(data, list)
        except Exception as e:
            logger.error(f"HackerNews health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.http_client.close()

    async def __aenter__(self) -> "HackerNewsExtractor":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()
