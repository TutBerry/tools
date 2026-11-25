"""Run notification and cache invalidation consumers."""
import logging
import os
import signal
import time

import django
import pika
from django.conf import settings

from tutberry.adapters.rabbitmq_consumer import RabbitMqConsumer
from tutberry.adapters.smtp_mail import SmtpMail
from tutberry.adapters.valkey_cache import client_for
from tutberry.adapters.valkey_processed_events import ValkeyProcessedEvents
from tutberry.workers.cache_invalidator import CacheInvalidationHandler
from tutberry.workers.notification_handler import NotificationHandler

logger = logging.getLogger(__name__)


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tutberry.settings")
    django.setup()
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from tutberry.tracing import configure_tracing
    configure_tracing('tutberry-worker')
    PsycopgInstrumentor().instrument()
    from tutberry.workers.outbox_relay import relay_one
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
            cache_client = client_for(settings.CACHE_URL)
            consumer = RabbitMqConsumer(
                connection.channel(), "booking.notifications",
                NotificationHandler(SmtpMail(settings.SMTP_HOST, settings.SMTP_PORT)),
                processed=ValkeyProcessedEvents(cache_client),
                max_attempts=settings.NOTIFICATION_MAX_ATTEMPTS,
                lease_seconds=settings.PROCESSING_LEASE_SECONDS,
                keep_seconds=settings.PROCESSED_EVENTS_TTL_HOURS * 3600,
            )
            consumer.setup()
            invalidator = RabbitMqConsumer(connection.channel(), "booking.cache", CacheInvalidationHandler(cache_client))
            invalidator.setup()
            relay = connection.channel()
            relay.confirm_delivery()
            while not stopping:
                relay_one(relay)
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
