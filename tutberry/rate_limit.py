"""Atomic shared token bucket, fail open on optional cache outage."""
from django.conf import settings
from redis.exceptions import RedisError

from tutberry.adapters.valkey_cache import client_for

SCRIPT = """
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2])/1000000
local v = redis.call('HMGET', KEYS[1], 'tokens', 'time')
local tokens = math.min(10, tonumber(v[1] or 10) + math.max(0, now-tonumber(v[2] or now)))
local allowed = 0
if tokens >= 1 then tokens = tokens-1; allowed = 1 end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'time', now)
redis.call('EXPIRE', KEYS[1], 60)
return allowed
"""

def allow_booking(user_id):
    client = client_for(settings.CACHE_URL)
    try:
        return bool(client.eval(SCRIPT, 1, f"rate:booking:{user_id}"))
    except RedisError:
        return True
    finally:
        client.close()
