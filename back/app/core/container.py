from functools import lru_cache

from fastapi import Depends

from app.components.mongo_client import MongoComponent
from app.components.redis_client import RedisComponent
from app.components.s3_client import S3Component
from app.core.config import Settings, get_settings
from app.repositories.file_metadata_repository import FileMetadataRepository
from app.services.file_service import FileService
from app.services.normalization_profile_loader import NormalizationProfileLoader
from app.services.normalization_service import NormalizationService
from pipeline_ml.normalization_stage.dynamic_engine import DynamicNormalizationEngine
from pipeline_ml.normalization_stage.traceability import NormalizationTraceabilityService
from app.services.patient_service import PatientService


class Container:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.mongo = MongoComponent(settings)
        self.redis = RedisComponent(settings)
        self.s3 = S3Component(settings)

    def file_repository(self) -> FileMetadataRepository:
        return FileMetadataRepository(self.mongo.collection)

    def file_service(self) -> FileService:
        return FileService(
            settings=self.settings,
            repository=self.file_repository(),
            s3_component=self.s3,
            redis_component=self.redis,
        )

    def normalization_profile_loader(self) -> NormalizationProfileLoader:
        return NormalizationProfileLoader(
            settings=self.settings,
            redis_component=self.redis,
            mongo_component=self.mongo,
        )

    def normalization_service(self) -> NormalizationService:
        return NormalizationService(
            profile_loader=self.normalization_profile_loader(),
            settings=self.settings,
            dynamic_engine=DynamicNormalizationEngine(),
            traceability_service=NormalizationTraceabilityService(
                settings=self.settings,
                redis_component=self.redis,
                mongo_component=self.mongo,
                s3_component=self.s3,
            ),
        )

    def patient_service(self) -> PatientService:
        return PatientService(
            settings=self.settings,
            repository=self.file_repository(),
            s3_component=self.s3,
        )


@lru_cache
def _build_container() -> Container:
    return Container(get_settings())


def get_container() -> Container:
    return _build_container()


def get_file_service(container: Container = Depends(get_container)) -> FileService:
    return container.file_service()


def get_normalization_service(
    container: Container = Depends(get_container),
) -> NormalizationService:
    return container.normalization_service()


def get_patient_service(container: Container = Depends(get_container)) -> PatientService:
    return container.patient_service()


def get_normalization_profile_loader(
    container: Container = Depends(get_container),
) -> NormalizationProfileLoader:
    return container.normalization_profile_loader()
