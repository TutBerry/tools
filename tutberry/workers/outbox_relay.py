import json

import pika
from django.db import transaction
from django.utils import timezone
from opentelemetry import propagate, trace

from tutberry.adapters.rabbitmq_publisher import EXCHANGE
from tutberry.models import OutboxRecord


def relay_one(channel):
    with transaction.atomic():
        row = OutboxRecord.objects.select_for_update(skip_locked=True).filter(published_at__isnull=True).order_by("id").first()
        if row is None:
            return False
        with trace.get_tracer(__name__).start_as_current_span("outbox.publish", context=propagate.extract(row.headers)):
            headers = dict(row.headers)
            propagate.inject(headers)
            channel.basic_publish(exchange=EXCHANGE, routing_key=row.routing_key,
                                  body=json.dumps(row.payload).encode(),
                                  properties=pika.BasicProperties(delivery_mode=2, content_type="application/json",
                                                                  message_id=row.event_id, headers=headers), mandatory=True)
        row.published_at = timezone.now()
        row.save(update_fields=["published_at"])
        return True
