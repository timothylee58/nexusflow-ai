import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

AGENT_LOG_CHANNEL = "nexusflow:agent-log"
METRICS_CHANNEL = "nexusflow:metrics"


class InMemoryEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[str]]] = {}

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        message = json.dumps(payload)
        for queue in self._subscribers.get(channel, []):
            await queue.put(message)

    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.setdefault(channel, []).append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[channel].remove(queue)


class RedisService:
    def __init__(self) -> None:
        self._client = None
        self._fallback = InMemoryEventBus()
        self._use_redis = False

    async def connect(self) -> None:
        if not settings.redis_url:
            logger.warning("REDIS_URL not set — using in-memory event bus for SSE")
            return

        try:
            import redis.asyncio as redis

            self._client = redis.from_url(settings.redis_url, decode_responses=True)
            await self._client.ping()
            self._use_redis = True
            logger.info("Connected to Redis for SSE pub/sub")
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — falling back to in-memory bus", exc)
            self._client = None
            self._use_redis = False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        message = json.dumps(payload)
        if self._use_redis and self._client is not None:
            await self._client.publish(channel, message)
            return
        await self._fallback.publish(channel, payload)

    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        if self._use_redis and self._client is not None:
            pubsub = self._client.pubsub()
            await pubsub.subscribe(channel)
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        yield message["data"]
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            return

        async for message in self._fallback.subscribe(channel):
            yield message


redis_service = RedisService()
