"""Cache search results by all validated query parameters."""
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


def cache_key(values):
    encoded = json.dumps(values, sort_keys=True, default=str).encode()
    return "listings:" + hashlib.sha256(encoded).hexdigest()


def cached_search(values, cache, ttl, load):
    if ttl <= 0:
        return load()
    key = cache_key(values)
    cached = cache.get(key)
    if cached is not None:
        logger.debug("cache_hit %s", key)
        return cached
    logger.debug("cache_miss %s", key)
    result = load()
    cache.set(key, result, ttl)
    return result
