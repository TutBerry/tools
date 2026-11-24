"""Durable RabbitMQ publishing with broker confirmations."""
import json
import logging
from dataclasses import asdict

import pika

from tutberry.domain.events import DomainEvent

from tutberry.workers.cache_invalidator import CACHE_INVALIDATION_BINDINGS

EXCHANGE = "booking.events"

QUEUES = {"booking.notifications": ("booking.*",), "booking.cache": CACHE_INVALIDATION_BINDINGS}
logger = logging.getLogger(__name__)


def setup_topology(channel):
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    for queue, bindings in QUEUES.items():
        channel.queue_declare(queue=queue + ".dlq", durable=True)
        channel.queue_declare(queue=queue, durable=True, arguments={
            "x-dead-letter-exchange": "", "x-dead-letter-routing-key": queue + ".dlq",
        })
        for key in bindings:
            channel.queue_bind(queue=queue, exchange=EXCHANGE, routing_key=key)


class RabbitMqEventBus:
    def __init__(self, url: str):
        self.url = url

    def publish(self, event: DomainEvent) -> None:
        params = pika.URLParameters(self.url)
        params.connection_attempts = 1
        params.socket_timeout = 1
        params.stack_timeout = 2
        params.blocked_connection_timeout = 2
        connection = pika.BlockingConnection(params)
        try:
            channel = connection.channel()
            setup_topology(channel)
            channel.confirm_delivery()
            channel.basic_publish(
                exchange=EXCHANGE, routing_key=event.routing_key,
                body=json.dumps(asdict(event), default=str).encode(),
                properties=pika.BasicProperties(
                    content_type="application/json", delivery_mode=2,
                    message_id=event.event_id,
                    headers={"event_type": type(event).__name__},
                ), mandatory=True,
            )
            logger.info("event_published %s %s", event.event_id, event.routing_key)
        finally:
            connection.close()
