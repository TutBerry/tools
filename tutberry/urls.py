from django.urls import path

from tutberry.api_booking import create_booking
from tutberry.api_search import list_available_listings
from tutberry.metrics import metrics
from tutberry.readiness import ready
from tutberry.views import health, version

urlpatterns = [path('ready', ready), path('metrics', metrics), path('health', health), path('version', version), path('api/bookings', create_booking), path('api/listings', list_available_listings)]
