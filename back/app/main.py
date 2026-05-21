import logging

from fastapi import FastAPI

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.container import get_container
from fastapi.middleware.cors import CORSMiddleware
settings = get_settings()



logging.basicConfig(
	level=logging.DEBUG if settings.normalization_debug_enabled else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
