import threading
import time
from dataclasses import dataclass, field

from cartag.errors import too_many


class WindowLimiter:
    """Per-key fixed-window counter, kept in memory.

    That is correct for a single server process. If the app is ever run as several processes, move
    this to a shared store. Per-account and per-phone limits live in the database and are always shared.
    """

    def __init__(self, limit: int, window_seconds: int, message: str, enabled: bool = True):
        self.limit = limit
        self.window = window_seconds
        self.message = message
        self.enabled = enabled
        self._hits: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def _current(self, key: str, now: float) -> tuple[float, int]:
        started, count = self._hits.get(key, (now, 0))
        if now - started >= self.window:
            return now, 0
        return started, count

    def consume(self, key: str) -> None:
        """Counts one request and raises 429 once the limit is passed."""
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            started, count = self._current(key, now)
            count += 1
            self._hits[key] = (started, count)
            if len(self._hits) > 50_000:  # keep memory bounded
                self._hits = {k: v for k, v in self._hits.items() if now - v[0] < self.window}
        if count > self.limit:
            raise too_many(self.message)

    def check(self, key: str) -> None:
        """Raises 429 if the key has already used up its allowance, without counting."""
        if not self.enabled:
            return
        with self._lock:
            _, count = self._current(key, time.monotonic())
        if count >= self.limit:
            raise too_many(self.message)

    def record(self, key: str) -> None:
        """Counts one event without raising (used for failed lookups)."""
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            started, count = self._current(key, now)
            self._hits[key] = (started, count + 1)


@dataclass
class Limiters:
    """Per-IP limits.

    They are generous on purpose: many mobile users in Pakistan share one carrier IP (CGNAT), so a
    tight per-IP limit would block innocent people. Abuse of a single phone number or account is
    limited separately in the database.
    """

    enabled: bool = True
    api: WindowLimiter = field(init=False)
    auth: WindowLimiter = field(init=False)
    otp: WindowLimiter = field(init=False)
    scan: WindowLimiter = field(init=False)
    scan_miss: WindowLimiter = field(init=False)
    activate: WindowLimiter = field(init=False)

    def __post_init__(self) -> None:
        on = self.enabled
        self.api = WindowLimiter(600, 60, "Too many requests. Please slow down.", on)
        self.auth = WindowLimiter(60, 600, "Too many login attempts. Please try again later.", on)
        self.otp = WindowLimiter(30, 3600, "Too many code requests. Please try again later.", on)
        self.scan = WindowLimiter(300, 60, "Too many requests. Please slow down.", on)
        self.scan_miss = WindowLimiter(30, 600, "Too many unknown codes. Please try again later.", on)
        self.activate = WindowLimiter(60, 3600, "Too many activation attempts. Please try again later.", on)
