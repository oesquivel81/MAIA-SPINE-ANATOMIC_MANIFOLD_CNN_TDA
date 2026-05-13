from fastapi import APIRouter

from app.api.v1.files_controller import router as files_router
from app.api.v1.health_controller import router as health_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router, tags=["health"])
api_v1_router.include_router(files_router, prefix="/files", tags=["files"])
