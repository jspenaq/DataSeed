"""
GitHub data extractor for fetching repository and release information.

This module implements the GitHubExtractor class that fetches data from the GitHub API,
including trending repositories, releases, and other relevant project information.
"""

import hashlib
from datetime import datetime
from typing import Any

import redis.asyncio as redis
from loguru import logger

from app.core.extractors.base import BaseExtractor, ExtractorConfig, RawItem
from app.core.http_client import RateLimitedClient
from app.core.redis import RedisClient
from app.core.registry import register_extractor


@register_extractor("github")
class GitHubExtractor(BaseExtractor):
    """
    Extractor for GitHub API data.

    Fetches trending repositories, releases, and project information from GitHub's
    REST API. Handles rate limiting and authentication through the base HTTP client.
    """

    def __init__(
        self, config: ExtractorConfig, http_client: RateLimitedClient | None = None, source_id: int | None = None
    ):
        super().__init__(config)
        self.http_client = http_client or self.get_http_client()
        # Get GitHub token from configuration
        self.token = self.extractor_config.get("token")
        self.search_endpoint = self.extractor_config.get("search_endpoint", "/search/repositories")

        # Read mode from config, defaulting to "search"
        self.mode = self.extractor_config.get("mode", "search")

        # If mode is "releases", read repositories list from config
        if self.mode == "releases":
            self.repositories = self.extractor_config.get("repositories")
            if not self.repositories:
                logger.error("Releases mode requires 'repositories' list in config")
                raise ValueError("Releases mode requires 'repositories' list in config")
        else:
            self.repositories = None

        # Initialize normalizer if source_id is provided
        if source_id is not None:
            from app.core.registry import get_normalizer

            self.normalizer = get_normalizer("github", source_id)
        else:
            self.normalizer = None

        # Initialize Redis client for ETag caching
        self.redis: redis.Redis | None = None

        # Add default headers for GitHub API
        self.http_client.default_headers.update(
            {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "DataSeed/1.0 (https://github.com/jspenaq/dataseed)",
            }
        )
        if self.token:
            self.http_client.default_headers["Authorization"] = f"Bearer {self.token}"

    def _get_cache_key(self, url: str) -> str:
        """
        Generate a unique Redis key for a given API request URL.

        Args:
            url: The API request URL

        Returns:
            A unique cache key for the URL
        """
        url_hash = hashlib.sha1(url.encode()).hexdigest()
        return f"github:etag:{url_hash}"

    async def _get_redis_client(self) -> redis.Redis:
        """
        Get or initialize the Redis client.

        Returns:
            Redis client instance
        """
        if self.redis is None:
            self.redis = await RedisClient.get_redis()
        return self.redis

    async def fetch_recent(self, since: datetime | None = None, limit: int = 100) -> list[RawItem]:
        """
        Fetch recent items from GitHub.

        Args:
            since: Only fetch items published after this datetime
            limit: Maximum number of items to fetch

        Returns:
            List of raw items from GitHub
        """
        if self.mode == "search":
            return await self._fetch_search_mode(since, limit)
        elif self.mode == "releases":
            return await self._fetch_releases_mode(since, limit)
        else:
            logger.error(f"Unknown mode: {self.mode}")
            return []

    async def _fetch_search_mode(self, since: datetime | None = None, limit: int = 100) -> list[RawItem]:
        """
        Fetch repositories using search mode with conditional requests using ETags.
        """
        logger.info(f"Fetching recent GitHub repositories (limit: {limit}, since: {since})")

        try:
            # Format the since datetime for GitHub API query
            if since is None:
                # Default to last 24 hours if no since date provided
                from datetime import timedelta

                since = datetime.now() - timedelta(days=1)

            # Format datetime to GitHub API format: YYYY-MM-DDTHH:MM:SSZ
            since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Construct search query for repositories pushed after the since date
            query = f"pushed:>{since_str}"

            # Build the request URL with query parameters
            per_page = min(limit, 100)  # GitHub API max is 100 per page
            url = f"{self.base_url}{self.search_endpoint}?q={query}&sort=updated&order=desc&per_page={per_page}"

            # Generate cache key for this request
            cache_key = self._get_cache_key(url)

            # Try to get cached ETag from Redis
            cached_etag = None
            try:
                redis_client = await self._get_redis_client()
                cached_etag = await redis_client.get(cache_key)
                if cached_etag:
                    logger.debug(f"Found cached ETag for {url}: {cached_etag}")
            except Exception as e:
                logger.warning(f"Failed to retrieve cached ETag from Redis: {e}")

            # Prepare request headers
            headers = {}
            if cached_etag:
                headers["If-None-Match"] = cached_etag

            logger.info(f"Making request to {url} with query: {query}")

            # Make the request with conditional headers and get full response
            response = await self.http_client.get_with_response(url, headers=headers)

            if response is None:
                logger.error("Failed to fetch GitHub repositories")
                return []

            # Handle 304 Not Modified response
            if response.status_code == 304:
                logger.info("Received 304 Not Modified - content unchanged, returning empty list")
                return []

            # Try to cache the new ETag if present in response headers
            try:
                etag = response.headers.get("ETag")
                if etag:
                    redis_client = await self._get_redis_client()
                    # Set a 24-hour expiration for the cache
                    await redis_client.setex(cache_key, 86400, etag)
                    logger.debug(f"Cached new ETag for {url}: {etag}")
            except Exception as e:
                logger.warning(f"Failed to cache ETag in Redis: {e}")

            # Parse JSON response
            try:
                response_data = response.json()
            except Exception as e:
                logger.error(f"Failed to parse JSON response: {e}")
                return []

            # Handle successful response
            if isinstance(response_data, dict) and "items" in response_data:
                raw_items = response_data["items"]
                logger.info(f"Successfully fetched {len(raw_items)} GitHub repositories")

                # Normalize the raw items using the normalizer if available
                if self.normalizer is not None:
                    normalized_items = []
                    for raw_item in raw_items:
                        try:
                            normalized_item = self.normalizer.normalize(raw_item)
                            normalized_items.append(normalized_item)
                        except Exception as e:
                            logger.warning(
                                f"Failed to normalize repository {raw_item.get('full_name', 'unknown')}: {e}"
                            )
                            continue

                    logger.info(f"Successfully normalized {len(normalized_items)} repositories")
                    return normalized_items
                else:
                    logger.warning("No normalizer available, returning raw items")
                    return raw_items
            else:
                logger.error(f"Unexpected response format from GitHub API: {type(response_data)}")
                return []

        except Exception as e:
            logger.error(f"Error fetching GitHub repositories: {e}")
            return []

    async def _fetch_releases_mode(self, since: datetime | None = None, limit: int = 100) -> list[RawItem]:
        """
        Fetch releases from configured repositories with conditional requests using ETags.
        """
        # Type guard: we know repositories is not None in releases mode due to __init__ validation
        if not self.repositories:
            logger.error("No repositories configured for releases mode")
            return []

        logger.info(f"Fetching releases from {len(self.repositories)} repositories (limit: {limit}, since: {since})")

        all_releases = []

        for repo_full_name in self.repositories:
            try:
                logger.info(f"Fetching releases for repository: {repo_full_name}")

                # Construct the API URL for the releases endpoint
                url = f"{self.base_url}/repos/{repo_full_name}/releases"

                # Generate cache key for this request
                cache_key = self._get_cache_key(url)

                # Try to get cached ETag from Redis
                cached_etag = None
                try:
                    redis_client = await self._get_redis_client()
                    cached_etag = await redis_client.get(cache_key)
                    if cached_etag:
                        logger.debug(f"Found cached ETag for {url}: {cached_etag}")
                except Exception as e:
                    logger.warning(f"Failed to retrieve cached ETag from Redis: {e}")

                # Prepare request headers
                headers = {}
                if cached_etag:
                    headers["If-None-Match"] = cached_etag

                # Make the request with conditional headers and get full response
                response = await self.http_client.get_with_response(url, headers=headers)

                if response is None:
                    logger.warning(f"Failed to fetch releases for {repo_full_name}")
                    continue

                # Handle 304 Not Modified response
                if response.status_code == 304:
                    logger.info(f"Received 304 Not Modified for {repo_full_name} - content unchanged, skipping")
                    continue

                # Try to cache the new ETag if present in response headers
                try:
                    etag = response.headers.get("ETag")
                    if etag:
                        redis_client = await self._get_redis_client()
                        # Set a 24-hour expiration for the cache
                        await redis_client.setex(cache_key, 86400, etag)
                        logger.debug(f"Cached new ETag for {url}: {etag}")
                except Exception as e:
                    logger.warning(f"Failed to cache ETag in Redis: {e}")

                # Parse JSON response
                try:
                    response_data = response.json()
                except Exception as e:
                    logger.error(f"Failed to parse JSON response for {repo_full_name}: {e}")
                    continue

                if not isinstance(response_data, list):
                    logger.warning(f"Unexpected response format for {repo_full_name}: {type(response_data)}")
                    continue

                # Filter releases by since date if provided
                filtered_releases = []
                for release in response_data:
                    if since is not None:
                        # Parse the published_at date from the release
                        published_at_str = release.get("published_at")
                        if published_at_str:
                            try:
                                from datetime import datetime, timezone

                                published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                                # Ensure both datetimes are timezone-aware for comparison
                                if since.tzinfo is None:
                                    since = since.replace(tzinfo=timezone.utc)
                                if published_at <= since:
                                    continue  # Skip releases older than since date
                            except ValueError:
                                logger.warning(f"Could not parse published_at date: {published_at_str}")

                    # Add repository full name to the release object
                    release["repository_full_name"] = repo_full_name
                    filtered_releases.append(release)

                # Extend all_releases with the decorated release items
                all_releases.extend(filtered_releases)
                logger.info(f"Successfully fetched {len(filtered_releases)} releases from {repo_full_name}")

            except Exception as e:
                logger.error(f"Error fetching releases for {repo_full_name}: {e}")
                continue  # Continue with other repositories

        # Normalize the raw releases using the normalizer if available
        if self.normalizer is not None:
            normalized_releases = []
            for raw_release in all_releases:
                try:
                    normalized_release = self.normalizer.normalize(raw_release)
                    normalized_releases.append(normalized_release)
                except Exception as e:
                    repo_name = raw_release.get("repository_full_name", "unknown")
                    release_name = raw_release.get("name") or raw_release.get("tag_name", "unknown")
                    logger.warning(f"Failed to normalize release {release_name} from {repo_name}: {e}")
                    continue

            logger.info(f"Successfully normalized {len(normalized_releases)} releases")
            return normalized_releases[:limit]  # Respect the limit parameter
        else:
            logger.warning("No normalizer available, returning raw releases")
            return all_releases[:limit]

    async def fetch_batch(self, limit: int = 100) -> list[RawItem]:
        """
        Fetch a batch of items from GitHub.

        Args:
            limit: Maximum number of items to fetch

        Returns:
            List of raw items from GitHub
        """
        return await self.fetch_recent(limit=limit)

    async def health_check(self) -> bool:
        """
        Check if the GitHub API is accessible.

        Returns:
            True if GitHub API is accessible, False otherwise
        """
        try:
            url = f"{self.base_url}/rate_limit"
            headers = {"Accept": "application/vnd.github.v3+json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            response = await self.http_client.get_json(url, headers=headers)
            return response is not None and isinstance(response, dict)
        except Exception as e:
            logger.error(f"GitHub health check failed: {e}")
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
