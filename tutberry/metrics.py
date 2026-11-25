"""Bounded HTTP metric labels."""
from django.http import HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
DURATION = Histogram("http_request_duration_seconds", "HTTP duration", ["method", "route"], buckets=(.005,.01,.025,.05,.1,.25,.5,1,2,5,10))

def metrics(request):
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
