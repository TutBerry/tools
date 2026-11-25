"""Readiness distinguishes essential and optional dependencies."""
import pika
from django.conf import settings
from django.db import connection
from django.http import JsonResponse

from tutberry.adapters.valkey_cache import client_for

def database_probe():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")

def cache_probe():
    client = client_for(settings.CACHE_URL)
    try:
        client.ping()
    finally:
        client.close()

def broker_probe():
    params = pika.URLParameters(settings.BROKER_URL)
    params.connection_attempts = 1
    params.socket_timeout = 1
    params.stack_timeout = 2
    broker = pika.BlockingConnection(params)
    broker.close()

def ready(request):
    checks = {}
    overall = "ok"
    for name, essential, probe in (
        ("database", True, database_probe),
        ("cache", False, cache_probe),
        ("broker", False, broker_probe),
    ):
        try:
            probe()
            state = "ok"
        except Exception:  # noqa: BLE001 - dependency failures are readiness results
            state = "unavailable" if essential else "degraded"
        checks[name] = {"status": state}
        if state == "unavailable" or (state == "degraded" and overall == "ok"):
            overall = state
    return JsonResponse({"status": overall, "checks": checks, "version": settings.APP_VERSION}, status=503 if overall == "unavailable" else 200)
