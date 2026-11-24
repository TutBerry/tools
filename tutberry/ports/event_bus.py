from typing import Protocol

from tutberry.domain.events import DomainEvent


class EventBus(Protocol):
    def publish(self, event: DomainEvent) -> None: ...
