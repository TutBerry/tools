"""Bounded HTTP metric labels."""
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from django.http import HttpResponse

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
DURATION = Histogram("http_request_duration_seconds", "HTTP duration", ["method", "route"], buckets=(.005,.01,.025,.05,.1,.25,.5,1,2,5,10))

def metrics(request):
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
