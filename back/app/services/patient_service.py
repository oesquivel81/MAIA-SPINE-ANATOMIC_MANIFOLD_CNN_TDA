import logging
from datetime import datetime, UTC
from uuid import uuid4

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool

from app.components.s3_client import S3Component
from app.core.config import Settings
from app.repositories.file_metadata_repository import FileMetadataRepository

logger = logging.getLogger(__name__)


class PatientService:
    def __init__(
        self,
        settings: Settings,
        repository: FileMetadataRepository,
        s3_component: S3Component,
    ):
        self._settings = settings
        self._repository = repository
        self._s3_component = s3_component

    async def upload_patient_image(
        self,
        file: UploadFile,
        nombre: str,
        apellido_paterno: str,
        edad: int,
        peso: float,
        sexo: str,
        fecha: str,
    ) -> dict:
        self._s3_component.ensure_bucket()

        extension = file.filename.split(".")[-1] if "." in file.filename else "bin"
        object_key = f"patients/{uuid4()}.{extension}"
        content = await file.read()

        await run_in_threadpool(
            self._s3_component.client.put_object,
            Bucket=self._settings.aws_s3_bucket,
            Key=object_key,
            Body=content,
            ContentType=file.content_type,
        )

        metadata = {
            "nombre": nombre,
            "apellido_paterno": apellido_paterno,
            "edad": edad,
            "peso": peso,
            "sexo": sexo,
            "fecha": fecha,
            "file_name": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(content),
            "s3_bucket": self._settings.aws_s3_bucket,
            "s3_key": object_key,
            "image_url": None,
            "created_at": datetime.now(UTC).isoformat(),
        }

        saved = await self._repository.save(metadata)
        logger.info(f"Paciente guardado con id={saved['id']}, s3_key={object_key}")
        return saved
