from unittest.mock import Mock

import pytest
from django.test import Client


@pytest.mark.parametrize("failed,status,code", [(None,"ok",200),("cache","degraded",200),("broker","degraded",200),("database","unavailable",503)])
def test_readiness(monkeypatch, failed, status, code):
    for name in ("database","cache","broker"):
        probe = Mock(side_effect=OSError("offline") if name == failed else None)
        monkeypatch.setattr(f"tutberry.readiness.{name}_probe", probe)
    response = Client().get("/ready")
    assert response.status_code == code
    assert response.json()["status"] == status
    assert Client().get("/health").status_code == 200


@pytest.mark.django_db
def test_metrics():
    client = Client()
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"http_requests_total" in response.content
