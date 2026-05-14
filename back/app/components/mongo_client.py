import logging

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import Settings

logger = logging.getLogger(__name__)


class MongoComponent:
    def __init__(self, settings: Settings):
        logger.info(f"Inicializando MongoComponent con URI: {settings.mongo_uri}")
        self._settings = settings
        self._client = AsyncIOMotorClient(settings.mongo_uri)
        logger.debug(f"MongoComponent conectado a BD: {settings.mongo_db}")

    @property
    def collection(self):
        database = self._client[self._settings.mongo_db]
        logger.debug(f"Accediendo a colección por defecto: {self._settings.mongo_collection}")
        return database[self._settings.mongo_collection]

    def collection_by_name(self, collection_name: str):
        logger.debug(f"Accediendo a colección: {collection_name}")
        database = self._client[self._settings.mongo_db]
        return database[collection_name]
