import time

import redis.asyncio as redis


class RateLimiter:
    """
    Token-bucket rate limiter using Redis for distributed storage.

    The token bucket algorithm allows for burst traffic up to the bucket capacity
    while maintaining a steady refill rate over time.
    """

    def __init__(self, capacity: int, refill_rate: float, redis_client: redis.Redis):
        """
        Initialize the rate limiter.

        Args:
            capacity: Maximum number of tokens in the bucket
            refill_rate: Number of tokens added per second
            redis_client: Redis client for storage
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.redis_client = redis_client

    async def is_allowed(self, identifier: str) -> tuple[bool, int, float]:
        """
        Check if a request is allowed for the given identifier.

        Args:
            identifier: Unique identifier for the client (API key or IP)

        Returns:
            Tuple of (is_allowed, remaining_tokens, reset_time)
        """
        current_time = time.time()
        tokens_key = f"rl:{identifier}:tokens"
        timestamp_key = f"rl:{identifier}:ts"

        # Use a pipeline for atomic operations
        pipe = self.redis_client.pipeline()
        pipe.get(tokens_key)
        pipe.get(timestamp_key)
        results = await pipe.execute()

        current_tokens = results[0]
        last_timestamp = results[1]

        if current_tokens is None or last_timestamp is None:
            # First request for this identifier - initialize with full capacity
            current_tokens = self.capacity - 1  # Consume one token for this request
            reset_time = current_time + (self.capacity / self.refill_rate)

            # Store the initial state
            pipe = self.redis_client.pipeline()
            pipe.set(tokens_key, current_tokens, ex=3600)  # Expire after 1 hour of inactivity
            pipe.set(timestamp_key, current_time, ex=3600)
            await pipe.execute()

            return True, int(current_tokens), reset_time

        # Convert stored values
        current_tokens = float(current_tokens)
        last_timestamp = float(last_timestamp)

        # Calculate tokens to add based on elapsed time
        time_elapsed = current_time - last_timestamp
        tokens_to_add = time_elapsed * self.refill_rate

        # Update token count (capped at capacity)
        new_tokens = min(self.capacity, current_tokens + tokens_to_add)

        if new_tokens >= 1.0:
            # Allow the request and consume one token
            new_tokens -= 1.0

            # Update Redis with new values
            pipe = self.redis_client.pipeline()
            pipe.set(tokens_key, new_tokens, ex=3600)
            pipe.set(timestamp_key, current_time, ex=3600)
            await pipe.execute()

            # Calculate reset time (when bucket will be full again)
            tokens_needed = self.capacity - new_tokens
            reset_time = current_time + (tokens_needed / self.refill_rate)

            return True, int(new_tokens), reset_time
        # Not enough tokens - deny the request
        # Don't update timestamp since no token was consumed
        pipe = self.redis_client.pipeline()
        pipe.set(tokens_key, new_tokens, ex=3600)
        await pipe.execute()

        # Calculate when the next token will be available
        tokens_needed = 1.0 - new_tokens
        reset_time = current_time + (tokens_needed / self.refill_rate)

        return False, 0, reset_time
