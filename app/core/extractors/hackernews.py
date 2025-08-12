import asyncio
from datetime import datetime, timezone
from typing import Any, cast

import httpx
from loguru import logger

from app.core.extractors.base import BaseExtractor, ExtractorConfig, RawItem


class HackerNewsExtractor(BaseExtractor):
    """HackerNews API extractor using httpx for async operations."""

    def __init__(self, config: ExtractorConfig):
        super().__init__(config)
        self.client: httpx.AsyncClient | None = None
        self.items_endpoint = self.extractor_config.get("items_endpoint", "/topstories.json")
        self.detail_endpoint = self.extractor_config.get("detail_endpoint", "/item/{id}.json")

        # Rate limiting: HN doesn't have strict limits but be respectful
        self.request_delay = 60 / self.rate_limit if self.rate_limit > 0 else 0.1

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proper configuration."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                headers={
                    "User-Agent": "DataSeed/1.0 (https://github.com/jspenaq/dataseed)",
                    "Accept": "application/json",
                },
            )
        return self.client

    async def _make_request(self, url: str, retries: int = 3) -> dict[str, Any] | None:
        """
        Make HTTP request with retry logic and rate limiting.

        Args:
            url: URL to request
            retries: Number of retry attempts

        Returns:
            JSON response data or None if failed
        """
        client = await self._get_client()

        for attempt in range(retries):
            try:
                # Rate limiting
                if self.request_delay > 0:
                    await asyncio.sleep(self.request_delay)

                response = await client.get(url)
                response.raise_for_status()

                return response.json()

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error {e.response.status_code} for {url}, attempt {attempt + 1}/{retries}")
                if e.response.status_code == 429:  # Rate limited
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                elif e.response.status_code >= 500:  # Server error
                    await asyncio.sleep(1)
                else:
                    break  # Don't retry client errors

            except (httpx.RequestError, httpx.TimeoutException) as e:
                logger.warning(f"Request error for {url}: {e}, attempt {attempt + 1}/{retries}")
                await asyncio.sleep(2**attempt)

            except Exception as e:
                logger.error(f"Unexpected error for {url}: {e}")
                break

        logger.error(f"Failed to fetch {url} after {retries} attempts")
        return None

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
        story_ids = [int(item_id) for item_id in limited_data if isinstance(item_id, (int, str))]
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
        return await self._make_request(url)

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

            if not isinstance(timestamp, (int, float)):
                logger.warning(f"Timestamp is not a number for item {item_id}")
                return None

            # Convert timestamp to datetime
            published_at = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)

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

    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
