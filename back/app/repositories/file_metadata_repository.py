from typing import Any

from bson import ObjectId
from bson.errors import InvalidId


class FileMetadataRepository:
    def __init__(self, collection):
        self._collection = collection

    async def save(self, metadata: dict[str, Any]) -> dict[str, Any]:
        result = await self._collection.insert_one(metadata)
        metadata["id"] = str(result.inserted_id)
        return metadata

    async def find_by_id(self, file_id: str):
        try:
            object_id = ObjectId(file_id)
        except InvalidId:
            return None

        document = await self._collection.find_one({"_id": object_id})
        if not document:
            return None
        document["id"] = str(document.pop("_id"))
        return document
