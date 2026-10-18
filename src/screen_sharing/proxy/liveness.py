"""Detect suspend and silent transport loss without timing out an idle picture."""
from __future__ import annotations

import time
from typing import Callable


# The native launcher treats this as a request to establish a fresh session.
RECONNECT_EXIT_CODE = 75


def suspend_clock() -> float:
    # Linux MONOTONIC excludes suspend; BOOTTIME includes it and is immune to
    # wall-clock/NTP adjustments. Other platforms use elapsed wall time.
    if hasattr(time, "CLOCK_BOOTTIME"):
        return time.clock_gettime(time.CLOCK_BOOTTIME)
    return time.time()


class ConnectionLiveness:
    def __init__(
        self,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        elapsed: Callable[[], float] = suspend_clock,
        timeout: float = 15.0,
    ) -> None:
        self._monotonic = monotonic
        self._elapsed = elapsed
        self.timeout = timeout
        self._last_tick = monotonic()
        self._last_elapsed = elapsed()
        self._last_received = self._last_tick

    def note_received(self) -> None:
        """Called only for decrypted peer traffic, including idle heartbeats."""
        self._last_received = self._monotonic()

    def check(self) -> str | None:
        now, elapsed = self._monotonic(), self._elapsed()
        tick_gap = now - self._last_tick
        sleep_gap = elapsed - self._last_elapsed - tick_gap
        self._last_tick, self._last_elapsed = now, elapsed
        if sleep_gap >= 2.0 or tick_gap >= self.timeout:
            return "local system resumed or session processing was paused"
        if now - self._last_received >= self.timeout:
            return "no response from the Mac for %.0f seconds" % self.timeout
        return None
