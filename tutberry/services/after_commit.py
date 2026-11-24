"""Publish only after successful database commit."""
import logging

from django.db import transaction

from tutberry.domain.events import BookingCreated, DomainEvent
from tutberry.ports.event_bus import EventBus

logger = logging.getLogger(__name__)


class AfterCommitEventBus:
    def __init__(self, target: EventBus):
        self.target = target

    def publish(self, event: DomainEvent) -> None:
        def deliver():
            try:
                self.target.publish(event)
            except Exception:
                logger.exception("event_publish_failed %s", event.event_id)
        transaction.on_commit(deliver)


class BookingEventNotifier:
    """Bridge the existing booking service port to domain events."""
    def __init__(self, events: EventBus):
        self.events = events

    def booking_created(self, booking):
        self.events.publish(BookingCreated(
            booking_id=booking.id, listing_id=booking.listing_id,
            tenant_id=booking.tenant_id, start_date=booking.period.start_date,
            end_date=booking.period.end_date,
        ))
