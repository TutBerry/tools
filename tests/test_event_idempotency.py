"""Consumer tests with a deterministic in-memory lease store."""
import json
from unittest.mock import Mock
from uuid import uuid4

import pika
from pytest import fixture

from tutberry.adapters.rabbitmq_consumer import RabbitMqConsumer
from tutberry.ports.processed_events import Claim
from tutberry.workers.cache_invalidator import CacheInvalidationHandler
from tutberry.workers.errors import TransientFailure
from tutberry.workers.notification_handler import NotificationHandler


class MemoryProcessed:
    def __init__(self):
        self.states = {}

    def claim(self, event_id, lease_seconds):
        if event_id in self.states:
            return self.states[event_id]
        self.states[event_id] = Claim.IN_PROGRESS
        return Claim.NEW

    def mark_done(self, event_id, keep_seconds):
        self.states[event_id] = Claim.DONE

    def release(self, event_id):
        self.states.pop(event_id, None)


@fixture
def worker():
    channel, mail = Mock(), Mock()
    processed = MemoryProcessed()
    handler = NotificationHandler(mail, lookup=lambda tenant: "tenant@example.test")
    consumer = RabbitMqConsumer(channel, "booking.notifications", handler, processed)
    return consumer, channel, mail, processed


def deliver(worker, event_id="e-1", kind="booking.created", attempt=1):
    consumer, channel, _, _ = worker
    payload = {"event_id": event_id, "tenant_id": str(uuid4()),
               "listing_id": str(uuid4()), "booking_id": str(uuid4()),
               "start_date": "2030-01-01", "end_date": "2030-01-02",
               "actor_id": str(uuid4()), "reason": "ремонт"}
    method = Mock(delivery_tag=1, routing_key=kind)
    properties = pika.BasicProperties(message_id=event_id, headers={"x-attempt": attempt})
    consumer.on_message(channel, method, properties, json.dumps(payload).encode())


def test_duplicate_delivery(worker):
    deliver(worker)
    deliver(worker)
    assert worker[2].send.call_count == 1
    assert worker[1].basic_ack.call_count == 2


def test_distinct_events(worker):
    deliver(worker, "e-1")
    deliver(worker, "e-2")
    assert worker[2].send.call_count == 2


def test_failed_processing_releases_lease(worker):
    _, channel, mail, processed = worker
    mail.send.side_effect = TransientFailure("offline")
    deliver(worker)
    assert "e-1" not in processed.states
    assert channel.basic_publish.call_args.kwargs["routing_key"] == "booking.notifications"
    mail.send.side_effect = None
    deliver(worker, attempt=2)
    assert processed.states["e-1"] is Claim.DONE
    assert mail.send.call_count == 2


def test_redelivery_after_simulated_lease_expiry(worker):
    _, _, mail, processed = worker
    processed.claim("e-1", 1)
    deliver(worker)
    mail.send.assert_not_called()
    processed.states.pop("e-1")
    deliver(worker)
    mail.send.assert_called_once()


def test_cancelled_event_skipped(worker):
    deliver(worker, kind="booking.cancelled")
    worker[2].send.assert_not_called()
    worker[1].basic_publish.assert_not_called()


def test_withdrawal_includes_reason(worker):
    deliver(worker, kind="booking.withdrawn")
    assert "ремонт" in worker[2].send.call_args.args[2]


def test_cache_invalidation_repeat():
    keys = {b"listings:a", b"listings:b"}
    client = Mock()
    client.scan_iter.side_effect = lambda **kwargs: iter(list(keys))
    client.delete.side_effect = keys.discard
    handler = CacheInvalidationHandler(client)
    for _ in range(2):
        handler.handle("booking.created", {"event_id": "e-1"})
    assert not keys


def test_exhausted_attempts_go_to_dlq(worker):
    worker[2].send.side_effect = TransientFailure("offline")
    deliver(worker, attempt=3)
    kwargs = worker[1].basic_publish.call_args.kwargs
    assert kwargs["routing_key"] == "booking.notifications.dlq"
    assert kwargs["properties"].headers["x-attempts"] == 3
