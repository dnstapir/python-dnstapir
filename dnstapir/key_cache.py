import logging
from abc import ABC, abstractmethod
from datetime import timedelta

import redis
from opentelemetry import trace
from pydantic import BaseModel, Field
from ttlru_map import TTLMap

tracer = trace.get_tracer("dnstapir.tracer")


class RedisSettings(BaseModel):
    host: str = Field(description="Redis hostname")
    port: int = Field(description="Redis port", default=6379)


class KeyCacheSettings(BaseModel):
    size: int = Field(description="Cache size", default=1000)
    ttl: int = Field(description="Cache TTL", default=300)
    redis: RedisSettings | None = None


def key_cache_from_settings(settings: KeyCacheSettings):
    if settings.redis:
        memory_key_cache = MemoryKeyCache(size=settings.size, ttl=settings.ttl) if settings.size else None
        redis_client = redis.StrictRedis(host=settings.redis.host, port=settings.redis.port)
        return RedisKeyCache(redis_client=redis_client, ttl=settings.ttl, memory_cache=memory_key_cache)
    elif settings.size:
        return MemoryKeyCache(size=settings.size, ttl=settings.ttl)
    else:
        return DummyKeyCache()


class KeyCache(ABC):
    def __init__(self):
        self.logger = logging.getLogger(__name__).getChild(self.__class__.__name__)

    @abstractmethod
    def get(self, key: str) -> bytes | None:
        return None

    @abstractmethod
    def set(self, key: str, value: bytes) -> None:
        pass


class DummyKeyCache(KeyCache):
    def get(self, key: str) -> bytes | None:
        return None

    def set(self, key: str, value: bytes) -> None:
        pass


class MemoryKeyCache(KeyCache):
    def __init__(self, size: int, ttl: int):
        super().__init__()
        self.cache = TTLMap(ttl=timedelta(seconds=ttl), max_size=size)
        self.logger.info("Configured memory key cache size=%d ttl=%d", size, ttl)

    def get(self, key: str) -> bytes | None:
        with tracer.start_as_current_span("memory_key_cache_get"):
            res = self.cache.get(key)
        self.logger.debug("Cache GET %s (%s)", key, "hit" if res else "miss")
        return res

    def set(self, key: str, value: bytes) -> None:
        self.logger.debug("Cache SET %s", key)
        with tracer.start_as_current_span("memory_key_cache_set"):
            self.cache[key] = value


class RedisKeyCache(KeyCache):
    def __init__(self, redis_client: redis.Redis, ttl: int, memory_cache: MemoryKeyCache | None = None):
        super().__init__()
        self.redis_client = redis_client
        self.ttl = ttl
        self.memory_cache = memory_cache
        self.logger.info("Configured Redis key cache ttl=%d", ttl)

    def get(self, key: str) -> bytes | None:
        if self.memory_cache and (res := self.memory_cache.get(key)):
            return res
        with tracer.start_as_current_span("redis_key_cache_get"):
            res = self.redis_client.get(name=key)
        self.logger.debug("Cache GET %s (%s)", key, "hit" if res else "miss")
        if res and self.memory_cache:
            self.memory_cache.set(key, res)
        return res

    def set(self, key: str, value: bytes) -> None:
        self.logger.debug("Cache SET %s", key)
        with tracer.start_as_current_span("redis_key_cache_set"):
            self.redis_client.set(name=key, value=value, ex=self.ttl)
        if self.memory_cache:
            self.memory_cache.set(key, value)
