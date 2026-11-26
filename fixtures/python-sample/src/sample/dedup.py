"""Request de-duplication: each request id's side effect is applied at most once.

Implements the design verified in fixtures/formal-sample/Dedup.tla (Atomic = TRUE):
ids are atomically *claimed*, then marked *done* after the effect is applied.
A duplicate of an in-flight id is not acknowledged (the client retries later),
which is what keeps AckedImpliesApplied true.
"""

from __future__ import annotations

import enum
import threading
from collections.abc import Callable, Hashable


class Outcome(enum.Enum):
    APPLIED = "applied"
    ALREADY_DONE = "already_done"
    IN_PROGRESS = "in_progress"

    @property
    def acknowledge(self) -> bool:
        """Whether the caller may acknowledge the request to the client."""
        return self is not Outcome.IN_PROGRESS


class DedupProcessor:
    def __init__(self, on_claimed: Callable[[Hashable], None] | None = None) -> None:
        self._claimed: set[Hashable] = set()
        self._done: set[Hashable] = set()
        self._lock = threading.Lock()
        # Test seam: runs between claiming an id and applying its effect, which is
        # the window in which the TLC counterexamples interleave a duplicate.
        self._on_claimed = on_claimed

    def process(self, request_id: Hashable, effect: Callable[[], None]) -> Outcome:
        with self._lock:
            if request_id in self._done:
                return Outcome.ALREADY_DONE
            if request_id in self._claimed:
                return Outcome.IN_PROGRESS
            self._claimed.add(request_id)
        try:
            if self._on_claimed is not None:
                self._on_claimed(request_id)
            effect()
        except BaseException:
            with self._lock:
                self._claimed.discard(request_id)
            raise
        with self._lock:
            self._done.add(request_id)
        return Outcome.APPLIED
