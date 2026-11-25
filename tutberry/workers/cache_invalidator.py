"""Invalidate all search variants after availability changes."""
import logging

from tutberry.adapters.valkey_cache import FAILURES
from tutberry.workers.errors import TransientFailure

logger = logging.getLogger(__name__)
CACHE_INVALIDATION_BINDINGS = ("booking.created", "booking.cancelled", "booking.withdrawn")


class CacheInvalidationHandler:
    def __init__(self, client):
        self.client = client

    def handle(self, routing_key, payload):
        if routing_key not in CACHE_INVALIDATION_BINDINGS:
            return
        try:
            # Search keys hash the entire filter set; invalidate every variant.
            for key in self.client.scan_iter(match="listings:*", count=100):
                self.client.delete(key)
        except FAILURES as exc:
            raise TransientFailure("Cache invalidation unavailable") from exc
        logger.info("cache_invalidated %s", payload["event_id"])
