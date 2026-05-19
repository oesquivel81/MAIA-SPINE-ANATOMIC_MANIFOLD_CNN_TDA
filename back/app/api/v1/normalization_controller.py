import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.container import get_normalization_profile_loader, get_normalization_service
from app.schemas.normalization_schema import (
    NormalizationResponse,
    ProfileBootstrapResponse,
    ProfileStorageStatusResponse,
)
from app.services.normalization_profile_loader import NormalizationProfileLoader
from app.services.normalization_service import NormalizationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/image", response_model=NormalizationResponse)
async def normalize_image(
    file: UploadFile = File(...),
    profile_source: str | None = Form(None),
    compare_file: UploadFile | None = File(None),
    compare_profile_json: UploadFile | None = File(None),
    normalization_service: NormalizationService = Depends(get_normalization_service),
):
    return await normalization_service.normalize_image(
        file=file,
        profile_source=profile_source,
        compare_file=compare_file,
        compare_profile_json=compare_profile_json,
    )


@router.post("/profiles/bootstrap", response_model=ProfileBootstrapResponse)
async def bootstrap_profiles(
    profile_loader: NormalizationProfileLoader = Depends(get_normalization_profile_loader),
):
    logger.info("Endpoint POST /profiles/bootstrap llamado")
    try:
        redis_loaded = await profile_loader.load_profiles_to_redis()
        logger.info(f"Bootstrap Redis completado: {redis_loaded} perfiles cargados")
        mongo_loaded = await profile_loader.load_profiles_to_mongo()
        logger.info(f"Bootstrap Mongo completado: {mongo_loaded} perfiles cargados")
        status = await profile_loader.get_storage_status()
        logger.debug(f"Estado de almacenamiento obtenido: {status}")
        return {
            "loaded_to_redis": redis_loaded,
            "loaded_to_mongo": mongo_loaded,
            "status": status,
        }
    except Exception as e:
        logger.error(f"Error en bootstrap_profiles: {str(e)}", exc_info=True)
        raise


@router.get("/profiles/status", response_model=ProfileStorageStatusResponse)
async def profiles_status(
    sample_size: int = 5,
    profile_loader: NormalizationProfileLoader = Depends(get_normalization_profile_loader),
):
    logger.info(f"Endpoint GET /profiles/status llamado (sample_size={sample_size})")
    try:
        status = await profile_loader.get_storage_status(sample_size=sample_size)
        logger.debug(f"Status obtenido: fuente={status['source_count']}, redis={status['redis_count']}, mongo={status['mongo_count']}")
        return status
    except Exception as e:
        logger.error(f"Error en profiles_status: {str(e)}", exc_info=True)
        return {
            "profiles_dir": str(profile_loader._profiles_dir),
            "index_file": str(profile_loader._index_jsonl),
            "source_count": len(profile_loader._read_profile_index_jsonl()),
            "source_sample_keys": [
                str(item.get("patient_key", "unknown"))
                for item in profile_loader._read_profile_index_jsonl()[:sample_size]
            ],
            "redis_key": profile_loader.PROFILE_INDEX_KEY,
            "redis_count": 0,
            "redis_sample_keys": [],
            "mongo_collection": profile_loader._settings.mongo_profiles_collection,
            "mongo_count": 0,
            "mongo_sample_keys": [],
            "default_profile_source": profile_loader.default_source,
        }
