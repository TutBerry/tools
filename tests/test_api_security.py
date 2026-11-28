from django.test import Client


def test_oversized_json_rejected():
    response = Client().post("/api/bookings", data=b"x" * (1024 * 1024 + 1), content_type="application/json")
    assert response.status_code == 413


def test_security_headers():
    response = Client().get("/health")
    assert response.status_code == 200
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"
