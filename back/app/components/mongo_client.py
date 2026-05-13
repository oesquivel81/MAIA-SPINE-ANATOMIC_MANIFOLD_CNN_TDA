from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import Settings


class MongoComponent:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = AsyncIOMotorClient(settings.mongo_uri)

    @property
    def collection(self):
        database = self._client[self._settings.mongo_db]
        return database[self._settings.mongo_collection]
