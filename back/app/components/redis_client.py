import logging

from redis.asyncio import Redis

from app.core.config import Settings

logger = logging.getLogger(__name__)


class RedisComponent:
    def __init__(self, settings: Settings):
        logger.info(f"Inicializando RedisComponent con URI: {settings.redis_uri}")
        self._client = Redis.from_url(settings.redis_uri, decode_responses=True)
        logger.debug("RedisComponent iniciado exitosamente")

    @property
    def client(self) -> Redis:
        return self._client
