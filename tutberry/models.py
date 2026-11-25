"""Persistence models. Domain rules live in tutberry.domain."""
import uuid

from django.db import models


class ListingRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id = models.UUIDField()
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=80, blank=True, default="")
    location = models.CharField(max_length=120, blank=True, default="")
    daily_rate = models.DecimalField(max_digits=12, decimal_places=2)
    deposit = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, default="draft")

    class Meta:
        indexes = [
            models.Index(fields=["status", "category", "location", "daily_rate"], name="listing_search_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(daily_rate__gte=0), name="listing_rate_nonnegative"),
            models.CheckConstraint(condition=models.Q(deposit__gte=0), name="listing_deposit_nonnegative"),
        ]


class BookingRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(ListingRecord, on_delete=models.PROTECT, related_name="bookings")
    tenant_id = models.UUIDField()
    start_date = models.DateField()
    end_date = models.DateField()
    rent = models.DecimalField(max_digits=12, decimal_places=2)
    deposit = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, default="pending")
    cancellation_reason = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F("start_date")), name="booking_valid_period"),
            models.CheckConstraint(condition=models.Q(rent__gte=0), name="booking_rent_nonnegative"),
            models.CheckConstraint(condition=models.Q(deposit__gte=0), name="booking_deposit_nonnegative"),
        ]


class ListingAvailabilityRecord(models.Model):
    """Owner-defined calendar blocks; independent of actual bookings."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(ListingRecord, on_delete=models.CASCADE, related_name="availability_blocks")
    start_date = models.DateField()
    end_date = models.DateField()
    is_blocked = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="availability_valid_period",
            ),
        ]
        indexes = [models.Index(fields=["listing", "start_date"], name="availability_listing_start_idx")]


class TransactionRecord(models.Model):
    """Payment ledger metadata; no real gateway integration yet."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(BookingRecord, on_delete=models.PROTECT, related_name="transactions")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=30)
    status = models.CharField(max_length=20, default="pending")
    payment_gateway_id = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gte=0), name="transaction_amount_nonnegative")]


class MessageRecord(models.Model):
    """Booking-linked messages; user UUIDs are not yet database foreign keys."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(BookingRecord, on_delete=models.PROTECT, related_name="messages")
    sender_id = models.UUIDField()
    receiver_id = models.UUIDField()
    text_content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class ReviewRecord(models.Model):
    """One review per author per booking."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(BookingRecord, on_delete=models.PROTECT, related_name="reviews")
    author_id = models.UUIDField()
    target_id = models.UUIDField()
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"),
            models.UniqueConstraint(fields=["booking", "author_id"], name="review_unique_booking_author"),
        ]


class UserProfileRecord(models.Model):
    """Optional profile extension of Django authentication user (expand phase)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="tutberry_profile")
    display_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32, blank=True)
    role = models.CharField(max_length=20, default="tenant")
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["tenant", "owner", "platform"]),
                name="profile_valid_role",
            ),
        ]


class OutboxRecord(models.Model):
    event_id = models.CharField(max_length=36, unique=True)
    routing_key = models.CharField(max_length=80)
    payload = models.JSONField()
    headers = models.JSONField(default=dict)
    published_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["id"], condition=models.Q(published_at__isnull=True), name="outbox_unpublished_idx")]
