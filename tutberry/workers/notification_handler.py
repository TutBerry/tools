"""Translate booking events into email notifications."""
import logging
from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth import get_user_model
from django.db import OperationalError

from tutberry.workers.errors import PermanentFailure, TransientFailure

logger = logging.getLogger(__name__)


def find_email(tenant_id):
    # Existing API derives domain IDs from Django integer user IDs.
    try:
        for pk, email in get_user_model().objects.values_list("pk", "email").iterator():
            if uuid5(NAMESPACE_URL, f"tutberry:user:{pk}") == tenant_id:
                return email or None
    except OperationalError as exc:
        raise TransientFailure("User database unavailable") from exc
    return None


class NotificationHandler:
    def __init__(self, mail, lookup=find_email):
        self.mail, self.lookup = mail, lookup

    def handle(self, routing_key, payload):
        if routing_key not in ("booking.created", "booking.withdrawn"):
            return
        try:
            tenant = UUID(payload["tenant_id"])
            listing = UUID(payload["listing_id"])
            booking = UUID(payload["booking_id"])
            start = date.fromisoformat(payload["start_date"])
            end = date.fromisoformat(payload["end_date"])
            if end < start:
                raise ValueError("Invalid period")
            reason = payload["reason"] if routing_key == "booking.withdrawn" else ""
            if routing_key == "booking.withdrawn":
                UUID(payload["actor_id"])
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError("Missing reason")
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise PermanentFailure("Invalid booking payload") from exc
        email = self.lookup(tenant)
        if not email:
            raise PermanentFailure("Recipient email not found")
        subject = "Заявка на аренду создана" if routing_key == "booking.created" else "Бронирование снято"
        body = f"Бронь {booking}. Инструмент {listing}. Период: {start} — {end}."
        if reason:
            body += f" Причина: {reason}."
        self.mail.send(email, subject, body)
        logger.info("event_processed %s", payload["event_id"])
