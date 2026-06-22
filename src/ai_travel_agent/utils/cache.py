import functools
import hashlib
import json
import logging
from typing import Any

from cachetools import TTLCache

from ai_travel_agent.utils.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    def __init__(self) -> None:
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._connect()
        return self._client

    def _connect(self) -> Any:
        if settings.use_fake_redis:
            return self._fake_client()

        try:
            import redis

            client: Any = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            return client

        except Exception:
            return self._fake_client()

    @staticmethod
    def _fake_client() -> Any:
        import fakeredis

        return fakeredis.FakeRedis(decode_responses=True)

    def get(self, namespace: str, params: dict[str, Any]) -> Any | None:
        key = self._make_key(namespace, params)
        raw = self.client.get(key)
        return json.loads(raw) if raw else None

    def set(
        self, namespace: str, params: dict[str, Any], value: Any, ttl: int = 3600
    ) -> None:
        key = self._make_key(namespace, params)
        self.client.setex(key, ttl, json.dumps(value, default=str))

    def _make_key(self, namespace: str, params: dict[str, Any]) -> str:
        raw = json.dumps(params, sort_keys=True, default=str)
        return f"{namespace}:{hashlib.md5(raw.encode()).hexdigest()[:12]}"

    def is_healthy(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def clear(self) -> None:
        try:
            self.client.flushall()
        except Exception:
            pass


cache = CacheManager()


def get_redis_client() -> Any:
    return cache.client


_local_cache: TTLCache = TTLCache(maxsize=512, ttl=300)


def _make_cache_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Create a stable cache key from function arguments."""
    payload = json.dumps(
        {"a": list(args), "k": kwargs},
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:20]
    return f"{prefix}:{digest}"


def tiered_cache(ttl: int, key_prefix: str):
    """
    Two-level read-through cache.

    L1:
        cachetools TTLCache (in-process)

    L2:
        Redis (shared across workers)

    Flow:
        L1 hit -> return
        L2 hit -> populate L1 and return
        miss -> execute function -> store in both
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            key = _make_cache_key(key_prefix, args, kwargs)

            # L1 cache hit
            if key in _local_cache:
                return _local_cache[key]

            # L2 cache hit
            try:
                redis = get_redis_client()
                raw = redis.get(key)

                if raw is not None:
                    value = json.loads(raw)

                    _local_cache[key] = value
                    return value

            except Exception:
                pass

            # Cache miss
            result = func(self, *args, **kwargs)

            # Save to L1
            _local_cache[key] = result

            # Save to L2
            try:
                redis = get_redis_client()
                redis.set(
                    key,
                    json.dumps(result, default=str),
                    ex=ttl,
                )
            except Exception:
                pass

            return result

        return wrapper

    return decorator
