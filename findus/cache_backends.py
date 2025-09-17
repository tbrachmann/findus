"""Custom cache backend for rate limiting with database storage."""

from typing import Optional

from django.core.cache.backends.db import DatabaseCache
from django.db import transaction


class RateLimitDatabaseCache(DatabaseCache):
    """Database cache backend with atomic increment support for rate limiting."""

    def incr(self, key: str, delta: int = 1, version: Optional[int] = None) -> int:
        """Increment cache value atomically using database transactions."""
        key = self.make_key(key, version=version)
        self.validate_key(key)

        with transaction.atomic():
            try:
                # Try to get the current value
                current_value = self.get(key, version=version)
                if current_value is None:
                    # Key doesn't exist, set it to delta
                    self.set(key, delta, version=version)
                    return delta
                else:
                    # Key exists, increment it
                    new_value = int(current_value) + delta
                    self.set(key, new_value, version=version)
                    return new_value
            except (ValueError, TypeError):
                # Value is not an integer, set it to delta
                self.set(key, delta, version=version)
                return delta

    def decr(self, key: str, delta: int = 1, version: Optional[int] = None) -> int:
        """Decrement cache value atomically."""
        return self.incr(key, -delta, version=version)
