"""Small in-memory sliding-window rate limiter (per key)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


def client_key(request) -> str:
    """Best-effort client id (works behind the Cloudflare tunnel too)."""
    fwd = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


class RateLimiter:
    """Allow at most ``limit`` recorded hits per ``window`` seconds, per key.

    Usage::

        wait = limiter.retry_after(key)   # 0 -> allowed, else seconds to wait
        ...
        limiter.hit(key)                  # record a failed try
    """

    def __init__(self, limit: int, window: float):
        self.limit = limit
        self.window = window
        self._hits: dict[object, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, q: deque[float], now: float) -> None:
        while q and now - q[0] >= self.window:
            q.popleft()

    def retry_after(self, key: object) -> int:
        now = time.monotonic()
        with self._lock:
            q = self._hits.get(key)
            if not q:
                return 0
            self._trim(q, now)
            if len(q) < self.limit:
                return 0
            return int(self.window - (now - q[0])) + 1

    def hit(self, key: object) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            self._trim(q, now)
            q.append(now)
            if len(self._hits) > 5000:  # keep memory bounded
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
                    del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
