"""Redis-backed cache for all travel agent API responses."""

import json
import hashlib
import logging
from typing import Optional, Any

from src.utils.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis-backed cache. Falls back to fakeredis when no Redis server is available."""

    def __init__(self) -> None:
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._connect()
        return self._client

    def _connect(self) -> Any:
        # Try real Redis first; fall back to fakeredis automatically on Windows dev
        if settings.use_fake_redis:
            return self._fake_client()
        try:
            import redis
            client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            logger.info("Connected to Redis at %s", settings.redis_url)
            return client
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — switching to fakeredis", exc)
            return self._fake_client()

    @staticmethod
    def _fake_client() -> Any:
        import fakeredis
        logger.info("Using fakeredis (in-memory, dev only)")
        return fakeredis.FakeRedis(decode_responses=True)

    def _make_key(self, namespace: str, params: dict) -> str:
        param_str = json.dumps(params, sort_keys=True)
        hash_str = hashlib.md5(param_str.encode()).hexdigest()[:12]
        return f"travel:{namespace}:{hash_str}"

    def get(self, namespace: str, params: dict) -> Optional[Any]:
        key = self._make_key(namespace, params)
        try:
            raw = self.client.get(key)
            if raw:
                logger.debug("Cache HIT: %s", key)
                return json.loads(raw)
            logger.debug("Cache MISS: %s", key)
            return None
        except Exception as exc:
            logger.warning("Cache GET failed: %s", exc)
            return None

    def set(self, namespace: str, params: dict, value: Any, ttl: int = 3600) -> bool:
        key = self._make_key(namespace, params)
        try:
            self.client.setex(key, ttl, json.dumps(value))
            logger.debug("Cache SET: %s (TTL=%ds)", key, ttl)
            return True
        except Exception as exc:
            logger.warning("Cache SET failed: %s", exc)
            return False

    def invalidate(self, namespace: str, params: dict) -> bool:
        key = self._make_key(namespace, params)
        try:
            self.client.delete(key)
            return True
        except Exception as exc:
            logger.warning("Cache DELETE failed: %s", exc)
            return False

    def is_healthy(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception:
            return False


# Singleton — import this everywhere
cache = CacheManager()
