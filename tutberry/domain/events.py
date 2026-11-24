"""Immutable rental booking events."""
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import ClassVar
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    routing_key: ClassVar[str]
    booking_id: UUID
    listing_id: UUID
    tenant_id: UUID
    start_date: date
    end_date: date
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True, kw_only=True)
class BookingCreated(DomainEvent):
    routing_key: ClassVar[str] = "booking.created"


@dataclass(frozen=True, slots=True, kw_only=True)
class BookingCancelled(DomainEvent):
    routing_key: ClassVar[str] = "booking.cancelled"
    reason: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class BookingWithdrawn(DomainEvent):
    routing_key: ClassVar[str] = "booking.withdrawn"
    actor_id: UUID
    reason: str
