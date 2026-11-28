"""Public listing search with database-side filtering and date availability."""
from django.conf import settings
from django.db.models import Exists, OuterRef
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from tutberry.adapters.valkey_cache import ValkeyCache, client_for
from tutberry.models import BookingRecord, ListingAvailabilityRecord, ListingRecord
from tutberry.services.listing_query import cached_search


class ListingSearchQuery(serializers.Serializer):
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    category = serializers.CharField(required=False, allow_blank=True, max_length=80)
    location = serializers.CharField(required=False, allow_blank=True, max_length=120)
    min_price = serializers.DecimalField(
        required=False, min_value=0, max_digits=12, decimal_places=2
    )
    max_price = serializers.DecimalField(
        required=False, min_value=0, max_digits=12, decimal_places=2
    )
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError("End date cannot precede start date")
        minimum, maximum = attrs.get("min_price"), attrs.get("max_price")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise serializers.ValidationError("Minimum price cannot exceed maximum price")
        return attrs


@api_view(["GET"])
@permission_classes([AllowAny])
def list_available_listings(request):
    if set(request.query_params) - set(ListingSearchQuery().fields):
        return Response({"detail": "Unexpected query parameters"}, status=400)
    params = ListingSearchQuery(data=request.query_params)
    params.is_valid(raise_exception=True)
    values = params.validated_data
    cache = ValkeyCache(client_for(settings.CACHE_URL))
    try:
        return Response(cached_search(values, cache, settings.LISTINGS_CACHE_TTL_SECONDS,
                                      lambda: load_listings(values)))
    finally:
        cache.client.close()


def load_listings(values):
    start, end = values["start_date"], values["end_date"]
    blocked = ListingAvailabilityRecord.objects.filter(
        listing_id=OuterRef("pk"),
        is_blocked=True,
        start_date__lte=end,
        end_date__gte=start,
    )
    reserved = BookingRecord.objects.filter(
        listing_id=OuterRef("pk"),
        status__in=["pending", "approved", "paid", "active"],
        start_date__lte=end,
        end_date__gte=start,
    )
    queryset = (
        ListingRecord.objects.filter(status="active")
        .annotate(has_block=Exists(blocked), has_reservation=Exists(reserved))
        .filter(has_block=False, has_reservation=False)
    )
    if values.get("category"):
        queryset = queryset.filter(category__iexact=values["category"])
    if values.get("location"):
        queryset = queryset.filter(location__iexact=values["location"])
    if "min_price" in values:
        queryset = queryset.filter(daily_rate__gte=values["min_price"])
    if "max_price" in values:
        queryset = queryset.filter(daily_rate__lte=values["max_price"])
    limit = values["limit"]
    # Stable ordering makes repeated searches predictable and enables indexing.
    listings = queryset.order_by("id").values(
        "id", "title", "category", "location", "daily_rate", "deposit"
    )[:limit]
    return {
        "items": [
            {
                "id": str(item["id"]),
                "title": item["title"],
                "category": item["category"],
                "location": item["location"],
                "daily_rate": str(item["daily_rate"]),
                "deposit": str(item["deposit"]),
            }
            for item in listings
        ],
        "limit": limit,
    }
