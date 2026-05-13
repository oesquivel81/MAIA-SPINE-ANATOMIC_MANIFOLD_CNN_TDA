from redis.asyncio import Redis

from app.core.config import Settings


class RedisComponent:
    def __init__(self, settings: Settings):
        self._client = Redis.from_url(settings.redis_uri, decode_responses=True)

    @property
    def client(self) -> Redis:
        return self._client
