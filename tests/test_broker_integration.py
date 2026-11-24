"""Opt-in integration checks against a dedicated RabbitMQ test instance."""
import os
from datetime import date
from uuid import uuid4

import pika
import pytest

from tutberry.adapters.rabbitmq_publisher import (
    QUEUES,
    RabbitMqEventBus,
    setup_topology,
)
from tutberry.domain.events import BookingCreated


@pytest.mark.skipif(not os.getenv("TEST_BROKER_URL"), reason="Dedicated test broker required")
def test_events_accumulate_without_worker():
    url = os.environ["TEST_BROKER_URL"]
    connection = pika.BlockingConnection(pika.URLParameters(url))
    try:
        channel = connection.channel()
        setup_topology(channel)
        for queue in QUEUES:
            channel.queue_purge(queue)
        events = [BookingCreated(booking_id=uuid4(), listing_id=uuid4(),
                    tenant_id=uuid4(), start_date=date(2030, 1, 1),
                    end_date=date(2030, 1, 2)) for _ in range(3)]
        for event in events:
            RabbitMqEventBus(url).publish(event)
        for queue in QUEUES:
            assert channel.queue_declare(queue, passive=True).method.message_count == 3
            received = set()
            for _ in events:
                method, properties, body = channel.basic_get(queue, auto_ack=False)
                assert method is not None
                assert body
                received.add(properties.message_id)
                channel.basic_ack(method.delivery_tag)
            assert received == {event.event_id for event in events}
            assert channel.queue_declare(queue, passive=True).method.message_count == 0
    finally:
        connection.close()
