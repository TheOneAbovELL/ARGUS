"""In-process sliding-window rate limiting.

Adequate for a single-process deployment. A multi-replica deployment would
need a shared store (e.g. Redis); that is intentionally out of scope.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from app.core.errors import RateLimitedError


class SlidingWindowRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        if limit < 1:
            raise ValueError("limit must be positive")
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, message: str = "Too many requests. Please slow down.") -> None:
        """Record one event for ``key`` or raise :class:`RateLimitedError`."""
        now = self._clock()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= self._max_keys:
                    self._evict(now)
                events = self._events.setdefault(key, deque())
            while events and now - events[0] >= self._window:
                events.popleft()
            if len(events) >= self._limit:
                retry_after = max(1, math.ceil(self._window - (now - events[0])))
                raise RateLimitedError(message, retry_after=retry_after)
            events.append(now)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def _evict(self, now: float) -> None:
        """Drop keys with no events in the window; if still full, drop 10% of
        the keys with the fewest recent events (oldest first). Keys at their
        limit are never evicted, so cycling throwaway keys cannot reset an
        active brute-force counter."""
        stale = [k for k, v in self._events.items() if not v or now - v[-1] >= self._window]
        for key in stale:
            del self._events[key]
        if len(self._events) >= self._max_keys:
            candidates = [k for k, v in self._events.items() if len(v) < self._limit]
            candidates.sort(key=lambda k: (len(self._events[k]), self._events[k][-1]))
            for key in candidates[: max(1, len(self._events) // 10)]:
                del self._events[key]
