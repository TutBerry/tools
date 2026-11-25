"""Failure-path tests without requiring live auxiliary services."""
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from redis.exceptions import ConnectionError
from rest_framework.test import APIClient

from tutberry.adapters.valkey_cache import ValkeyCache
from tutberry.models import BookingRecord, ListingRecord, OutboxRecord
from tutberry.services.listing_query import cached_search
from tutberry.workers.cache_invalidator import CacheInvalidationHandler


def test_cache_aside_hit():
    cache = Mock()
    cache.get.return_value = None
    load = Mock(return_value={"items": []})
    assert cached_search({}, cache, 5, load) == {"items": []}
    cache.get.return_value = {"items": []}
    assert cached_search({}, cache, 5, load) == {"items": []}
    load.assert_called_once()


def test_invalidation_removes_search_variants():
    client = Mock()
    client.scan_iter.return_value = [b"listings:a", b"listings:b"]
    CacheInvalidationHandler(client).handle("booking.created", {"event_id": "test"})
    assert client.delete.call_count == 2


@pytest.mark.django_db
def test_search_without_cache(monkeypatch):
    broken = Mock()
    broken.get.side_effect = ConnectionError("offline")
    broken.set.side_effect = ConnectionError("offline")
    monkeypatch.setattr("tutberry.api_search.client_for", lambda url: broken)
    ListingRecord.objects.create(owner_id=uuid4(), title="Drill",
        daily_rate=Decimal(500), deposit=Decimal(100), status="active")
    response = APIClient().get("/api/listings?start_date=2030-01-01&end_date=2030-01-02")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    broken.get.assert_called_once()
    broken.set.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_booking_survives_broker_failure(monkeypatch):
    publish = Mock(side_effect=OSError("broker offline"))
    monkeypatch.setattr("tutberry.adapters.rabbitmq_publisher.RabbitMqEventBus.publish", publish)
    user = User.objects.create_user(username="resilience-tenant")
    listing = ListingRecord.objects.create(owner_id=uuid4(), title="Saw",
        daily_rate=Decimal(500), deposit=Decimal(100), status="active")
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post("/api/bookings", {"listing_id": str(listing.id),
        "start_date": "2030-01-01", "end_date": "2030-01-02"}, format="json")
    assert response.status_code == 201
    assert BookingRecord.objects.filter(pk=response.json()["id"]).exists()
    publish.assert_not_called()
    assert OutboxRecord.objects.filter(payload__booking_id=response.json()["id"], published_at__isnull=True).exists()


def test_cache_adapter_failure():
    client = Mock()
    client.get.side_effect = ConnectionError("offline")
    client.set.side_effect = ConnectionError("offline")
    client.delete.side_effect = ConnectionError("offline")
    cache = ValkeyCache(client)
    assert cache.get("key") is None
    cache.set("key", {}, 5)
    cache.delete("key")
