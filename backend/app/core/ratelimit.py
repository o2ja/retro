"""Sliding-window rate limiting for sensitive endpoints.

# ponytail: in-process memory, so limits are per worker. Move the counters to
# Redis only once the API actually runs on more than one process.
"""

import time
from collections import defaultdict, deque

from app.core.errors import RateLimitError

_hits: dict[str, deque[float]] = defaultdict(deque)


def enforce(key: str, *, limit: int, window_seconds: int) -> None:
    """Raise RateLimitError when `key` exceeded `limit` hits in the window."""
    now = time.monotonic()
    bucket = _hits[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= limit:
        raise RateLimitError
    bucket.append(now)


def reset(key: str | None = None) -> None:
    """Clear one key (e.g. after a successful login) or everything (tests)."""
    if key is None:
        _hits.clear()
    else:
        _hits.pop(key, None)
