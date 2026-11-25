"""Authenticated booking endpoint using server-side listing prices."""
import uuid

from django.db import transaction
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tutberry.adapters.sql_booking import SqlBookingRepository
from tutberry.api_errors import problem
from tutberry.domain.booking import BookingError
from tutberry.models import ListingAvailabilityRecord, ListingRecord
from tutberry.services.after_commit import BookingEventNotifier
from tutberry.services.outbox import OutboxEventBus
from tutberry.services.booking_service import BookingRequest, BookingService


class CreateBookingSerializer(serializers.Serializer):
    listing_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class UuidGenerator:
    def new_id(self):
        return uuid.uuid4()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_booking(request):
    data = CreateBookingSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    values = data.validated_data
    with transaction.atomic():
        try:
            listing = ListingRecord.objects.select_for_update().get(
                id=values["listing_id"], status="active"
            )
        except ListingRecord.DoesNotExist:
            return Response(problem(404, "Not Found", "Active listing not found"), status=404, content_type="application/problem+json")

        # Django's integer user ID is converted into a stable domain UUID.
        tenant_id = uuid.uuid5(uuid.NAMESPACE_URL, f"tutberry:user:{request.user.pk}")
        if listing.owner_id == tenant_id:
            return Response(problem(403, "Forbidden", "Cannot book your own listing"), status=403, content_type="application/problem+json")
        # The listing row is locked for this transaction. Owner-side calendar
        # writes must take the same lock to serialize changes with bookings.
        blocked = ListingAvailabilityRecord.objects.filter(
            listing=listing,
            is_blocked=True,
            start_date__lte=values["end_date"],
            end_date__gte=values["start_date"],
        ).exists()
        if blocked:
            return Response(
                problem(409, "Conflict", "Selected dates are blocked by the owner"),
                status=409,
                content_type="application/problem+json",
            )
        service = BookingService(SqlBookingRepository(), UuidGenerator(), BookingEventNotifier(OutboxEventBus()))
        try:
            booking = service.create(
                BookingRequest(
                    listing_id=listing.id,
                    tenant_id=tenant_id,
                    start_date=values["start_date"],
                    end_date=values["end_date"],
                    daily_rate=listing.daily_rate,
                    deposit=listing.deposit,
                )
            )
        except BookingError as exc:
            return Response(problem(409 if "unavailable" in str(exc).lower() else 400, "Conflict" if "unavailable" in str(exc).lower() else "Bad Request", str(exc)), status=409 if "unavailable" in str(exc).lower() else 400, content_type="application/problem+json")

    return Response(
        {"id": str(booking.id), "status": booking.status.value, "rent": str(booking.price.rent), "deposit": str(booking.price.deposit), "total": str(booking.price.total)},
        status=status.HTTP_201_CREATED,
    )
