from enum import Enum
from typing import Protocol


class Claim(Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class ProcessedEvents(Protocol):
    """Deduplication storage: unavailability is a transient failure."""

    def claim(self, event_id: str, lease_seconds: int) -> Claim: ...
    def mark_done(self, event_id: str, keep_seconds: int) -> None: ...
    def release(self, event_id: str) -> None: ...
