"""Opt-in checks against a dedicated Valkey service."""
import os
import time
from uuid import uuid4

import pytest

from tutberry.adapters.valkey_cache import ValkeyCache, client_for
from tutberry.adapters.valkey_processed_events import ValkeyProcessedEvents
from tutberry.ports.processed_events import Claim
from tutberry.workers.cache_invalidator import CacheInvalidationHandler

pytestmark = pytest.mark.skipif(not os.getenv("TEST_CACHE_URL"), reason="Dedicated Valkey required")


@pytest.fixture
def valkey():
    client = client_for(os.environ["TEST_CACHE_URL"])
    yield client
    client.close()


def test_atomic_lease_and_done(valkey):
    event = str(uuid4())
    first = ValkeyProcessedEvents(valkey)
    second = ValkeyProcessedEvents(valkey)
    try:
        assert first.claim(event, 60) is Claim.NEW
        assert second.claim(event, 60) is Claim.IN_PROGRESS
        first.mark_done(event, 86400)
        assert second.claim(event, 60) is Claim.DONE
    finally:
        valkey.delete(f"processed:{event}")


def test_expired_lease_recovered(valkey):
    event = str(uuid4())
    first = ValkeyProcessedEvents(valkey)
    second = ValkeyProcessedEvents(valkey)
    try:
        assert first.claim(event, 1) is Claim.NEW
        deadline = time.monotonic() + 3
        while valkey.exists(f"processed:{event}") and time.monotonic() < deadline:
            time.sleep(0.05)
        assert second.claim(event, 60) is Claim.NEW
        first.release(event)
        assert valkey.exists(f"processed:{event}")
        second.release(event)
        assert not valkey.exists(f"processed:{event}")
    finally:
        valkey.delete(f"processed:{event}")


def test_real_cache_invalidation(valkey):
    key = f"listings:{uuid4()}"
    cache = ValkeyCache(valkey)
    try:
        cache.set(key, {"items": []}, 5)
        assert cache.get(key) == {"items": []}
        CacheInvalidationHandler(valkey).handle("booking.created", {"event_id": str(uuid4())})
        assert cache.get(key) is None
    finally:
        valkey.delete(key)


def test_shared_booking_rate_limit(valkey, settings):
    from tutberry.rate_limit import allow_booking

    settings.CACHE_URL = os.environ["TEST_CACHE_URL"]
    user = str(uuid4())
    try:
        for _ in range(20):
            allowed, _, _ = allow_booking(user)
            assert allowed
        allowed, remaining, reset = allow_booking(user)
        assert not allowed
        assert remaining == 0
        assert 1 <= reset <= 3
        assert allow_booking(str(uuid4()))[0]
    finally:
        valkey.delete(f"rate:booking:{user}")
