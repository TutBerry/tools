"""Atomic deduplication lease; storage failure is not a cache miss."""
from uuid import uuid4

from tutberry.adapters.valkey_cache import FAILURES
from tutberry.ports.processed_events import Claim
from tutberry.workers.errors import TransientFailure


class ValkeyProcessedEvents:
    def __init__(self, client):
        self.client = client
        self.tokens = {}

    def claim(self, event_id, lease_seconds):
        key = f"processed:{event_id}"
        token = str(uuid4())
        try:
            if self.client.set(key, token, nx=True, ex=lease_seconds):
                self.tokens[event_id] = token
                return Claim.NEW
            return Claim.DONE if self.client.get(key) == b"done" else Claim.IN_PROGRESS
        except FAILURES as exc:
            raise TransientFailure("Deduplication store unavailable") from exc

    def mark_done(self, event_id, keep_seconds):
        token = self.tokens.get(event_id)
        try:
            result = self.client.eval(
                "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('SET', KEYS[1], 'done', 'EX', ARGV[2]) end return false",
                1, f"processed:{event_id}", token or "", keep_seconds)
            if not result:
                raise TransientFailure("Processing lease expired")
            self.tokens.pop(event_id, None)
        except FAILURES as exc:
            raise TransientFailure("Deduplication store unavailable") from exc

    def release(self, event_id):
        token = self.tokens.pop(event_id, None)
        if token is None:
            return
        try:
            self.client.eval(
                "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0",
                1, f"processed:{event_id}", token)
        except FAILURES as exc:
            raise TransientFailure("Deduplication store unavailable") from exc
