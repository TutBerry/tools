"""Cache-aside adapter: cache failure is a miss."""
import json
import logging

from redis import Redis
from redis.exceptions import ConnectionError, TimeoutError

logger = logging.getLogger(__name__)
FAILURES = (ConnectionError, TimeoutError)


def client_for(url):
    return Redis.from_url(url, socket_connect_timeout=0.2, socket_timeout=0.2, retry_on_timeout=False)


class ValkeyCache:
    def __init__(self, client):
        self.client = client

    def get(self, key):
        try:
            raw = self.client.get(key)
            return json.loads(raw) if raw is not None else None
        except (ConnectionError, TimeoutError, ValueError):
            logger.warning("cache_unavailable get")
            return None

    def set(self, key, value, ttl):
        if ttl <= 0:
            return
        try:
            self.client.set(key, json.dumps(value), ex=ttl)
        except FAILURES:
            logger.warning("cache_unavailable set")

    def delete(self, *keys):
        if not keys:
            return
        try:
            self.client.delete(*keys)
        except FAILURES:
            logger.warning("cache_invalidation_failed")
