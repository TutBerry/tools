"""Step 3: consume booking events in a separate process."""
import logging
import os
import signal
import time

import django
import pika

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tutberry.settings")
django.setup()

from django.conf import settings
from tutberry.adapters.rabbitmq_consumer import RabbitMqConsumer
from tutberry.adapters.valkey_cache import client_for
from tutberry.workers.cache_invalidator import CacheInvalidationHandler

logger = logging.getLogger(__name__)


class LoggingHandler:
    def handle(self, routing_key, payload):
        logger.info("event_received %s %s", payload["event_id"], routing_key)
        logger.info("event_processed %s", payload["event_id"])


def main():
    logging.basicConfig(level=settings.LOG_LEVEL.upper())
    stopping = False

    def stop(*args):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        connection = None
        cache_client = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(settings.BROKER_URL))
            consumer = RabbitMqConsumer(connection.channel(), "booking.notifications", LoggingHandler())
            consumer.setup()
            cache_client = client_for(settings.CACHE_URL)
            invalidator = RabbitMqConsumer(connection.channel(), "booking.cache", CacheInvalidationHandler(cache_client))
            invalidator.setup()
            while not stopping:
                connection.process_data_events(time_limit=1)
        except (pika.exceptions.AMQPError, OSError):
            logger.exception("worker_connection_failed")
            if not stopping:
                time.sleep(2)
        finally:
            if cache_client is not None:
                cache_client.close()
            if connection is not None and connection.is_open:
                connection.close()


if __name__ == "__main__":
    main()
