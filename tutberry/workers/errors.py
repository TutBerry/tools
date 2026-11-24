class TransientFailure(Exception):
    """Temporary failure; retry with backoff."""


class PermanentFailure(Exception):
    """Permanent failure; send to dead-letter queue."""


class LeaseHeld(TransientFailure):
    """Another delivery holds the lease; defer without consuming an attempt."""
