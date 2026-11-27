"""Bounded HTTP metric labels."""
import logging

from django.db import DatabaseError
from django.http import HttpResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
DURATION = Histogram("http_request_duration_seconds", "HTTP duration", ["method", "route"], buckets=(.005,.01,.025,.05,.1,.25,.3,.5,1,2,5,10))

def metrics(request):
    from django.utils import timezone

    from tutberry.models import OutboxRecord
    try:
        pending = OutboxRecord.objects.filter(published_at__isnull=True)
        OUTBOX_PENDING.set(pending.count())
        oldest = pending.order_by("created_at").first()
        OUTBOX_AGE.set((timezone.now()-oldest.created_at).total_seconds() if oldest else 0)
    except DatabaseError:
        logger.exception("outbox_metrics_unavailable")
        OUTBOX_PENDING.set(float("nan"))
        OUTBOX_AGE.set(float("nan"))
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)

OUTBOX_PENDING = Gauge("outbox_pending", "Unpublished events")
OUTBOX_AGE = Gauge("outbox_oldest_seconds", "Oldest unpublished event age")
READY = Gauge("service_ready", "Essential dependencies ready")
