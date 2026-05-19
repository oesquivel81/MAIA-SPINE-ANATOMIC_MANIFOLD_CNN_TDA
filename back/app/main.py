import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.container import get_container

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(api_v1_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event() -> None:
	logger.info("=== Iniciando aplicación ===")
	logger.info(f"normalization_bootstrap_on_startup={settings.normalization_bootstrap_on_startup}")
	if not settings.normalization_bootstrap_on_startup:
		logger.info("Bootstrap de perfiles deshabilitado en configuración")
		return

	try:
		logger.info("Iniciando bootstrap de perfiles de normalización...")
		container = get_container()
		loader = container.normalization_profile_loader()
		logger.debug("NormalizationProfileLoader obtenido del contenedor")
		await loader.load_profiles_to_redis()
		await loader.load_profiles_to_mongo()
		logger.info("✓ Bootstrap completado exitosamente")
	except Exception as e:
		logger.error(f"Error durante bootstrap: {str(e)}", exc_info=True)
		raise
