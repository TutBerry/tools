"""Manual acknowledgements and bounded retry delivery."""
import json
import logging
import random
from datetime import UTC, datetime
from typing import Protocol

import pika

from tutberry.adapters.rabbitmq_publisher import setup_topology
from tutberry.ports.processed_events import Claim
from tutberry.workers.errors import LeaseHeld, PermanentFailure, TransientFailure

logger = logging.getLogger(__name__)


class EventHandler(Protocol):
    def handle(self, routing_key: str, payload: dict) -> None: ...


class RabbitMqConsumer:
    def __init__(self, channel, queue, handler: EventHandler, processed=None,
                 max_attempts=3, lease_seconds=60, keep_seconds=86400):
        self.channel, self.queue, self.handler = channel, queue, handler
        self.processed = processed
        self.max_attempts, self.lease, self.keep = max_attempts, lease_seconds, keep_seconds

    def setup(self):
        setup_topology(self.channel)
        self.channel.basic_qos(prefetch_count=1)
        self.channel.confirm_delivery()
        self.channel.basic_consume(self.queue, self.on_message, auto_ack=False)

    def on_message(self, channel, method, properties, body):
        tag = method.delivery_tag
        headers = dict(properties.headers or {})
        kind = headers.get("x-original-routing-key", method.routing_key)
        attempt = 1
        claimed = False
        event_id = properties.message_id
        try:
            attempt = int(headers.get("x-attempt", 1))
            payload = json.loads(body)
            if attempt < 1 or not isinstance(payload, dict) or not event_id or payload.get("event_id") != event_id:
                raise PermanentFailure("Invalid event envelope")
            if self.processed is not None:
                claim = self.processed.claim(event_id, self.lease)
                if claim is Claim.DONE:
                    channel.basic_ack(tag)
                    return
                if claim is Claim.IN_PROGRESS:
                    raise LeaseHeld()
                claimed = True
            self.handler.handle(kind, payload)
            if claimed:
                self.processed.mark_done(event_id, self.keep)
        except Exception as exc:  # noqa: BLE001 - unknown handler failures go to DLQ
            if claimed:
                try:
                    self.processed.release(event_id)
                except TransientFailure:
                    logger.warning("dedup_release_failed %s", event_id)
            retry = isinstance(exc, TransientFailure) and (
                isinstance(exc, LeaseHeld) or attempt < self.max_attempts)
            headers["x-original-routing-key"] = kind
            if retry:
                delay = min(30, self.lease) if isinstance(exc, LeaseHeld) else random.uniform(0, min(30, 2 ** (attempt - 1)))
                logger.warning("event_retry_scheduled %s attempt=%s delay=%s", event_id, attempt, delay)
                channel.connection.sleep(delay)
                headers["x-attempt"] = attempt if isinstance(exc, LeaseHeld) else attempt + 1
                destination = self.queue
            else:
                headers.pop("x-attempt", None)
                headers.update({"x-attempts": attempt, "x-failure-kind": type(exc).__name__,
                                "x-failure-reason": str(exc)[:500],
                                "x-failed-at": datetime.now(UTC).isoformat()})
                destination = self.queue + ".dlq"
                logger.error("event_dead_lettered %s attempt=%s", event_id, attempt)
            try:
                channel.basic_publish(exchange="", routing_key=destination, body=body,
                    properties=pika.BasicProperties(content_type="application/json",
                        delivery_mode=2, message_id=event_id, headers=headers), mandatory=True)
            except (pika.exceptions.AMQPError, OSError):
                channel.basic_nack(tag, requeue=True)
                return
        channel.basic_ack(tag)
