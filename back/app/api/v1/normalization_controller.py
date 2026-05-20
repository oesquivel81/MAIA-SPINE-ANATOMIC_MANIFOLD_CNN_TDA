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
    trace_patient_name: str | None = Form(None),
    trace_patient_lastname: str | None = Form(None),
    trace_sex: str | None = Form(None),
    trace_age: int | None = Form(None),
    trace_weight: float | None = Form(None),
    trace_timestamp: str | None = Form(None),
    debug_save_json: bool | None = Form(None),
    trace_generate_visualization: bool | None = Form(None),
    normalization_service: NormalizationService = Depends(get_normalization_service),
):
    return await normalization_service.normalize_image(
        file=file,
        profile_source=profile_source,
        compare_file=compare_file,
        compare_profile_json=compare_profile_json,
        trace_patient_name=trace_patient_name,
        trace_patient_lastname=trace_patient_lastname,
        trace_sex=trace_sex,
        trace_age=trace_age,
        trace_weight=trace_weight,
        trace_timestamp=trace_timestamp,
        debug_save_json=debug_save_json,
        trace_generate_visualization=trace_generate_visualization,
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
        raise
