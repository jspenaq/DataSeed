"""
Shared API client for DataSeed Dashboard.

This module provides a reusable HTTP client for interacting with the FastAPI backend,
including retry logic, caching support, and proper error handling.
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
import streamlit as st

from dashboard.telemetry import track_api_call, track_rate_limit_event


class RateLimitError(Exception):
    """Custom exception for rate limiting scenarios."""

    def __init__(self, message: str, wait_time: float):
        super().__init__(message)
        self.wait_time = wait_time


class DataSeedAPIClient:
    """
    HTTP client for DataSeed API with caching and retry support.

    Features:
    - Automatic retries with exponential backoff
    - ETag-based caching support
    - User-Agent header for dashboard identification
    - Session state integration for caching
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.user_agent = "DataSeed-Dashboard/0.1.0"
        self.timeout = 30.0
        self.max_retries = 3
        self.base_retry_delay = 1.0  # Base delay for exponential backoff
        self.max_retry_delay = 60.0  # Maximum retry delay

        # Initialize cache and rate limiting state in session state
        if "api_cache" not in st.session_state:
            st.session_state.api_cache = {}
        if "api_etags" not in st.session_state:
            st.session_state.api_etags = {}
        if "rate_limit_state" not in st.session_state:
            st.session_state.rate_limit_state = {
                "backoff_until": None,
                "current_delay": self.base_retry_delay,
                "consecutive_429s": 0,
            }

    def _get_headers(self, endpoint: str) -> dict[str, str]:
        """Get headers for request including User-Agent and conditional ETag."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        # Add If-None-Match header if we have an ETag for this endpoint
        if endpoint in st.session_state.api_etags:
            headers["If-None-Match"] = st.session_state.api_etags[endpoint]

        return headers

    def _cache_response(self, endpoint: str, response: httpx.Response, data: Any) -> None:
        """Cache response data and ETag if present."""
        if "etag" in response.headers:
            st.session_state.api_etags[endpoint] = response.headers["etag"]
            st.session_state.api_cache[endpoint] = {
                "data": data,
                "cached_at": datetime.now(),
                "etag": response.headers["etag"],
            }

    def _get_cached_data(self, endpoint: str) -> Any | None:
        """Get cached data if available and not expired."""
        if endpoint not in st.session_state.api_cache:
            return None

        cache_entry = st.session_state.api_cache[endpoint]
        # Cache expires after 5 minutes
        if datetime.now() - cache_entry["cached_at"] > timedelta(minutes=5):
            return None

        return cache_entry["data"]

    def _check_rate_limit(self) -> float | None:
        """Check if we're currently rate limited and return wait time if so."""
        rate_limit_state = st.session_state.rate_limit_state

        if rate_limit_state["backoff_until"]:
            wait_time = rate_limit_state["backoff_until"] - time.time()
            if wait_time > 0:
                return wait_time
            # Rate limit period has passed, reset state
            rate_limit_state["backoff_until"] = None
            rate_limit_state["current_delay"] = self.base_retry_delay
            rate_limit_state["consecutive_429s"] = 0

        return None

    def _handle_rate_limit_response(self) -> float:
        """Handle 429 response and return backoff delay."""
        rate_limit_state = st.session_state.rate_limit_state
        rate_limit_state["consecutive_429s"] += 1

        # Exponential backoff: double the delay each time, up to max
        current_delay = min(
            rate_limit_state["current_delay"] * (2 ** (rate_limit_state["consecutive_429s"] - 1)),
            self.max_retry_delay,
        )

        rate_limit_state["current_delay"] = current_delay
        rate_limit_state["backoff_until"] = time.time() + current_delay

        return current_delay

    def _reset_rate_limit_state(self) -> None:
        """Reset rate limiting state after successful request."""
        rate_limit_state = st.session_state.rate_limit_state
        rate_limit_state["consecutive_429s"] = 0
        rate_limit_state["current_delay"] = self.base_retry_delay
        rate_limit_state["backoff_until"] = None

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request with retry logic, caching, and rate limiting."""
        # Check if we're currently rate limited
        wait_time = self._check_rate_limit()
        if wait_time:
            raise RateLimitError(f"Rate limited. Please wait {wait_time:.1f} seconds before retrying.", wait_time)

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(endpoint)

        # Track API call performance
        start_time = time.time()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.request(method=method, url=url, headers=headers, **kwargs)

                    # Calculate duration for telemetry
                    duration_ms = (time.time() - start_time) * 1000

                    # Handle 304 Not Modified - return cached data
                    if response.status_code == 304:
                        cached_data = self._get_cached_data(endpoint)
                        if cached_data:
                            # Reset rate limit state on successful cache hit
                            self._reset_rate_limit_state()
                            # Track successful cached API call
                            track_api_call(endpoint, method, duration_ms, 304, cache_hit=True)
                            return cached_data

                    # Handle 429 Too Many Requests
                    if response.status_code == 429:
                        backoff_delay = self._handle_rate_limit_response()
                        # Track rate limit event
                        rate_limit_state = st.session_state.rate_limit_state
                        track_rate_limit_event(backoff_delay, rate_limit_state["consecutive_429s"], endpoint)
                        raise RateLimitError(
                            f"Rate limited. Backing off for {backoff_delay:.1f} seconds.",
                            backoff_delay,
                        )

                    # Raise for other HTTP errors
                    response.raise_for_status()

                    # Parse JSON response
                    data = response.json()

                    # Cache successful responses and reset rate limit state
                    self._cache_response(endpoint, response, data)
                    self._reset_rate_limit_state()

                    # Track successful API call
                    track_api_call(endpoint, method, duration_ms, response.status_code, cache_hit=False)

                    return data

                except httpx.HTTPStatusError as e:
                    if e.response and e.response.status_code == 304:
                        # Handle 304 case
                        cached_data = self._get_cached_data(endpoint)
                        if cached_data:
                            self._reset_rate_limit_state()
                            duration_ms = (time.time() - start_time) * 1000
                            track_api_call(endpoint, method, duration_ms, 304, cache_hit=True)
                            return cached_data

                    if e.response and e.response.status_code == 429:
                        # Track rate limit event
                        rate_limit_state = st.session_state.rate_limit_state
                        duration_ms = (time.time() - start_time) * 1000
                        track_rate_limit_event(
                            rate_limit_state.get("current_delay", 1.0),
                            rate_limit_state.get("consecutive_429s", 1),
                            endpoint,
                        )
                        track_api_call(endpoint, method, duration_ms, 429, cache_hit=False)
                        # Don't retry 429s immediately, let the backoff handle it
                        raise

                    if attempt == self.max_retries - 1:
                        raise

                    # Wait before retry (exponential backoff)
                    await asyncio.sleep(2**attempt)

                except (httpx.RequestError, httpx.TimeoutException):
                    if attempt == self.max_retries - 1:
                        raise

                    # Wait before retry
                    await asyncio.sleep(2**attempt)

        raise Exception(f"Failed to make request after {self.max_retries} attempts")

    def get_rate_limit_status(self) -> dict[str, Any]:
        """Get current rate limiting status for UI display."""
        rate_limit_state = st.session_state.rate_limit_state

        if rate_limit_state["backoff_until"]:
            wait_time = max(0, rate_limit_state["backoff_until"] - time.time())
            return {
                "is_rate_limited": wait_time > 0,
                "wait_time_seconds": wait_time,
                "consecutive_429s": rate_limit_state["consecutive_429s"],
                "current_delay": rate_limit_state["current_delay"],
            }

        return {
            "is_rate_limited": False,
            "wait_time_seconds": 0,
            "consecutive_429s": 0,
            "current_delay": self.base_retry_delay,
        }

    async def get_health(self) -> dict[str, Any]:
        """Get API health status."""
        return await self._make_request("GET", "/api/v1/health")

    async def get_sources(self, status: str | None = None, search: str | None = None) -> dict[str, Any]:
        """Get available data sources with statistics."""
        params = {}
        if status:
            params["status"] = status
        if search:
            params["search"] = search

        return await self._make_request("GET", "/api/v1/sources/", params=params)

    async def get_source_details(self, source_id: int, runs_limit: int = 10) -> dict[str, Any]:
        """Get detailed information for a specific source."""
        params = {"runs_limit": runs_limit}
        return await self._make_request("GET", f"/api/v1/sources/{source_id}/", params=params)

    async def get_items(
        self,
        source: str | None = None,
        q: str | None = None,
        sort: str = "published_at",
        order: str = "desc",
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Get content items with filtering and pagination."""
        params = {"sort": sort, "order": order, "limit": limit}

        if source:
            params["source"] = source
        if q:
            params["q"] = q
        if cursor:
            params["cursor"] = cursor

        return await self._make_request("GET", "/api/v1/items/", params=params)

    async def get_stats(self, window: str = "24h", source_name: str | None = None) -> dict[str, Any]:
        """Get analytics and statistics."""
        params = {"window": window}
        if source_name:
            params["source_name"] = source_name
        return await self._make_request("GET", "/api/v1/items/stats", params=params)

    async def get_items_for_analytics(
        self,
        window: str = "24h",
        sources: list[str] | None = None,
        search_query: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get items data for analytics charts and export."""
        all_items = []
        cursor = None

        # Use cursor-based pagination for better performance
        while len(all_items) < limit:
            batch_limit = min(100, limit - len(all_items))

            # Get items for each source if specified, otherwise get all
            if sources and len(sources) == 1:
                # Single source - use source filter
                response = await self.get_items(source=sources[0], q=search_query, limit=batch_limit, cursor=cursor)
                items = response.get("items", [])
                all_items.extend(items)
                cursor = response.get("next_cursor")
                if not cursor or len(items) < batch_limit:
                    break
            else:
                # Multiple sources or all sources
                response = await self.get_items(q=search_query, limit=batch_limit, cursor=cursor)
                items = response.get("items", [])
                all_items.extend(items)
                cursor = response.get("next_cursor")
                if not cursor or len(items) < batch_limit:
                    break

        # Filter by sources if multiple specified
        if sources and len(sources) > 1:
            all_items = [item for item in all_items if item.get("source_id") in sources]

        return all_items[:limit]

    async def get_time_series_data(
        self,
        window: str = "24h",
        sources: list[str] | None = None,
        granularity: str = "hour",
    ) -> list[dict[str, Any]]:
        """Get time series data for charts."""
        # This would ideally be a dedicated endpoint, but for now we'll process items
        items = await self.get_items_for_analytics(window=window, sources=sources)

        # Group items by time period
        from collections import defaultdict
        from datetime import datetime

        time_buckets = defaultdict(int)

        # Determine bucket size based on granularity
        if granularity == "hour":
            bucket_minutes = 60
        elif granularity == "day":
            bucket_minutes = 1440  # 24 * 60
        else:
            bucket_minutes = 60  # default to hour

        for item in items:
            # Parse the published_at timestamp
            published_at = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))

            # Round down to the nearest bucket
            minutes_since_epoch = int(published_at.timestamp() / 60)
            bucket_start = (minutes_since_epoch // bucket_minutes) * bucket_minutes
            bucket_time = datetime.fromtimestamp(bucket_start * 60)

            time_buckets[bucket_time] += 1

        # Convert to list format for charts
        return [{"timestamp": timestamp, "count": count} for timestamp, count in sorted(time_buckets.items())]

    async def get_trending_items(
        self,
        window: str = "24h",
        source: str | None = None,
        limit: int = 10,
        use_hot_score: bool = False,
    ) -> list[dict[str, Any]]:
        """Get trending content items."""
        params = {"window": window, "limit": limit, "use_hot_score": use_hot_score}

        if source:
            params["source_name"] = source

        # The trending endpoint returns a list directly
        response = await self._make_request("GET", "/api/v1/items/trending", params=params)
        # Ensure we return a list even if the API returns something unexpected
        return response if isinstance(response, list) else []


# Global API client instance
# @st.cache_resource
def get_api_client() -> DataSeedAPIClient:
    """Get cached API client instance."""
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    return DataSeedAPIClient(base_url=base_url)


def run_async(coro):
    """Helper function to run async code in Streamlit."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)
