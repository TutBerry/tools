"""Manual acknowledgements and bounded retry delivery."""
import json
import random
import time
from typing import Protocol

import pika

from tutberry.adapters.rabbitmq_publisher import setup_topology
from tutberry.ports.processed_events import Claim
from tutberry.workers.errors import LeaseHeld, PermanentFailure


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
        attempt = int(headers.get("x-attempt", 1))
        claimed = False
        event_id = properties.message_id
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict) or not event_id or payload.get("event_id") != event_id:
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
            channel.basic_ack(tag)
            return
        except (ValueError, PermanentFailure):
            if claimed:
                self.processed.release(event_id)
            channel.basic_reject(tag, requeue=False)
            return
        except Exception as exc:
            if claimed:
                self.processed.release(event_id)
            if not isinstance(exc, LeaseHeld) and attempt >= self.max_attempts:
                channel.basic_reject(tag, requeue=False)
                return
            delay = min(30, self.lease) if isinstance(exc, LeaseHeld) else random.uniform(0, min(30, 2 ** attempt))
            # BlockingConnection.sleep services heartbeats during the wait.
            channel.connection.sleep(delay)
            headers.update({"x-original-routing-key": kind,
                            "x-attempt": attempt if isinstance(exc, LeaseHeld) else attempt + 1})
            try:
                channel.basic_publish(exchange="", routing_key=self.queue, body=body,
                    properties=pika.BasicProperties(content_type="application/json",
                        delivery_mode=2, message_id=event_id, headers=headers), mandatory=True)
            except Exception:
                channel.basic_nack(tag, requeue=True)
                return
            channel.basic_ack(tag)
