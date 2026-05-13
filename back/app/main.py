from fastapi import FastAPI

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.container import get_container

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(api_v1_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event() -> None:
	if not settings.normalization_bootstrap_redis_on_startup:
		return
	if settings.normalization_profile_source.lower() != "redis":
		return

	container = get_container()
	loader = container.normalization_profile_loader()
	await loader.load_profiles_to_redis()
