from fastapi import APIRouter

from app.api.v1.files_controller import router as files_router
from app.api.v1.health_controller import router as health_router
from app.api.v1.normalization_controller import router as normalization_router
from app.api.v1.patient_controller import router as patient_router


from app.api.v1.spine_analysis_controller import router as spine_router
api_v1_router = APIRouter()
api_v1_router.include_router(health_router, tags=["health"])
api_v1_router.include_router(files_router, prefix="/files", tags=["files"])
api_v1_router.include_router(normalization_router, prefix="/normalization", tags=["normalization"])
api_v1_router.include_router(patient_router, prefix="/patients", tags=["patients"])
api_v1_router.include_router(spine_router, prefix="/spine", tags=["spine-analysis"])