import json
from dataclasses import asdict

from django.db import connection
from opentelemetry import propagate

from tutberry.domain.events import DomainEvent
from tutberry.models import OutboxRecord


class OutboxEventBus:
    def publish(self, event: DomainEvent) -> None:
        if not connection.in_atomic_block:
            raise RuntimeError("Outbox requires a transaction")
        headers = {"event_type": type(event).__name__}
        propagate.inject(headers)
        OutboxRecord.objects.create(event_id=event.event_id, routing_key=event.routing_key,
                                    payload=json.loads(json.dumps(asdict(event), default=str)), headers=headers)
