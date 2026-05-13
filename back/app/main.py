from fastapi import FastAPI

from app.api.v1.router import api_v1_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(api_v1_router, prefix="/api/v1")
