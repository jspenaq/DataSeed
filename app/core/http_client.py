import asyncio
from typing import Any

import httpx
from loguru import logger


class RateLimitedClient:
    """
    HTTP client with rate limiting and retry logic.

    This class encapsulates httpx.AsyncClient and provides configurable
    rate limiting and retry mechanisms for making HTTP requests.
    """

    def __init__(
        self,
        rate_limit: int = 60,
        retries: int = 3,
        semaphore_size: int = 10,
        timeout: float = 30.0,
        max_connections: int = 10,
        max_keepalive_connections: int = 5,
        user_agent: str = "DataSeed/1.0",
        headers: dict[str, str] | None = None,
    ):
        """
        Initialize the rate-limited HTTP client.

        Args:
            rate_limit: Maximum requests per minute (0 for no limit)
            retries: Number of retry attempts for failed requests
            semaphore_size: Maximum number of concurrent requests
            timeout: Request timeout in seconds
            max_connections: Maximum number of connections
            max_keepalive_connections: Maximum number of keepalive connections
            user_agent: User-Agent header value
            headers: Additional headers to include in requests
        """
        self.rate_limit = rate_limit
        self.request_delay = 60 / rate_limit if rate_limit > 0 else 0.0
        self.client: httpx.AsyncClient | None = None

        # Client configuration
        self.retries = retries
        self.semaphore = asyncio.Semaphore(semaphore_size)
        self.timeout = timeout
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections

        # Default headers
        self.default_headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }
        if headers:
            self.default_headers.update(headers)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proper configuration."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(
                    max_connections=self.max_connections,
                    max_keepalive_connections=self.max_keepalive_connections,
                ),
                headers=self.default_headers,
            )
        return self.client

    async def get_json(self, url: str, retries: int | None = None, headers: dict[str, str] | None = None) -> dict[str, Any] | list[Any] | None:
        """
        Make HTTP GET request and return JSON response with retry logic and rate limiting.

        Args:
            url: URL to request
            retries: Number of retry attempts (uses instance default if None)
            headers: Additional headers for this request

        Returns:
            JSON response data or None if failed
        """
        response = await self.get_with_response(url, retries, headers)
        if response is None:
            return None
        
        # Handle 304 Not Modified
        if response.status_code == 304:
            return None
            
        try:
            return response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON response from {url}: {e}")
            return None

    async def get_with_response(self, url: str, retries: int | None = None, headers: dict[str, str] | None = None) -> httpx.Response | None:
        """
        Make HTTP GET request and return full response with retry logic and rate limiting.

        Args:
            url: URL to request
            retries: Number of retry attempts (uses instance default if None)
            headers: Additional headers for this request

        Returns:
            HTTP response or None if failed
        """
        if retries is None:
            retries = self.retries

        client = await self._get_client()

        async with self.semaphore:
            for attempt in range(retries):
                try:
                    # Rate limiting
                    if self.request_delay > 0:
                        await asyncio.sleep(self.request_delay)

                    # Merge additional headers with default headers
                    request_headers = self.default_headers.copy()
                    if headers:
                        request_headers.update(headers)

                    response = await client.get(url, headers=request_headers)
                    
                    # Don't raise for 304 Not Modified - it's a valid response for conditional requests
                    if response.status_code != 304:
                        response.raise_for_status()

                    return response

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

    async def get(self, url: str, retries: int | None = None) -> httpx.Response | None:
        """
        Make HTTP GET request with retry logic and rate limiting.

        Args:
            url: URL to request
            retries: Number of retry attempts (uses instance default if None)

        Returns:
            HTTP response or None if failed
        """
        if retries is None:
            retries = self.retries

        client = await self._get_client()

        async with self.semaphore:
            for attempt in range(retries):
                try:
                    # Rate limiting
                    if self.request_delay > 0:
                        await asyncio.sleep(self.request_delay)

                    response = await client.get(url)
                    response.raise_for_status()

                    return response

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
