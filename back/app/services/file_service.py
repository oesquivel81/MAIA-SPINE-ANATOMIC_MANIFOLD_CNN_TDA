import json
from datetime import datetime, UTC
from uuid import uuid4

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool

from app.components.redis_client import RedisComponent
from app.components.s3_client import S3Component
from app.core.config import Settings
from app.repositories.file_metadata_repository import FileMetadataRepository


class FileService:
    def __init__(
        self,
        settings: Settings,
        repository: FileMetadataRepository,
        s3_component: S3Component,
        redis_component: RedisComponent,
    ):
        self._settings = settings
        self._repository = repository
        self._s3_component = s3_component
        self._redis_component = redis_component

    async def upload_file(self, file: UploadFile):
        self._s3_component.ensure_bucket()

        extension = file.filename.split(".")[-1] if "." in file.filename else "bin"
        object_key = f"uploads/{uuid4()}.{extension}"
        content = await file.read()

        await run_in_threadpool(
            self._s3_component.client.put_object,
            Bucket=self._settings.aws_s3_bucket,
            Key=object_key,
            Body=content,
            ContentType=file.content_type,
        )

        metadata = {
            "file_name": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(content),
            "s3_bucket": self._settings.aws_s3_bucket,
            "s3_key": object_key,
            "created_at": datetime.now(UTC).isoformat(),
        }

        saved = await self._repository.save(metadata)
        await self._redis_component.client.setex(
            f"file:{saved['id']}",
            300,
            json.dumps(saved),
        )
        return saved

    async def get_file_metadata(self, file_id: str):
        cached = await self._redis_component.client.get(f"file:{file_id}")
        if cached:
            return {"cached": True, "payload": json.loads(cached)}

        data = await self._repository.find_by_id(file_id)
        if not data:
            return None

        await self._redis_component.client.setex(f"file:{file_id}", 300, json.dumps(data))
        return {"cached": False, "payload": data}
