from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.components.mongo_client import MongoComponent
from app.components.redis_client import RedisComponent
from app.core.config import Settings
from motor.motor_asyncio import AsyncIOMotorCollection
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class NormalizationProfileLoader:
    PROFILE_INDEX_KEY = "normalization_profiles:index:v1"
    PROFILE_COUNT_KEY = "normalization_profiles:count:v1"

    def __init__(
        self,
        settings: Settings,
        redis_component: RedisComponent,
        mongo_component: MongoComponent,
    ):
        self._settings = settings
        self._redis = redis_component
        self._mongo = mongo_component
        self._profiles_dir = (
            Path(__file__).resolve().parents[2]
            / "resources"
            / "NORMALIZATION_PROFILES"
        )
        self._index_jsonl = self._profiles_dir / "normalization_profile_index.jsonl"

    @property
    def redis_client(self) -> Redis:
        return self._redis.client

    @property
    def mongo_collection(self) -> AsyncIOMotorCollection:
        return self._mongo.collection_by_name(self._settings.mongo_profiles_collection)

    @property
    def default_source(self) -> str:
        return self._settings.normalization_profile_source.lower()

    async def load_profiles_to_redis(self) -> int:
        logger.info(f"Iniciando carga de perfiles a Redis desde {self._profiles_dir}")
        profiles = self._read_profile_index_jsonl()
        logger.debug(f"Se leyeron {len(profiles)} perfiles del archivo JSONL")
        await self.redis_client.set(self.PROFILE_INDEX_KEY, json.dumps(profiles))
        logger.debug(f"Perfiles guardados en Redis key: {self.PROFILE_INDEX_KEY}")
        await self.redis_client.set(self.PROFILE_COUNT_KEY, len(profiles))
        logger.info(f"✓ Cargados {len(profiles)} perfiles a Redis exitosamente")
        return len(profiles)

    async def get_profiles(self, source: str | None = None) -> list[dict[str, Any]]:
        selected_source = (source or self.default_source).lower()
        logger.debug(f"Obteniendo perfiles desde fuente: {selected_source}")
        if selected_source == "json":
            logger.debug("Leyendo perfiles desde JSON")
            return self._read_profile_index_jsonl()
        if selected_source == "redis":
            logger.debug("Leyendo perfiles desde Redis")
            return await self._read_profiles_from_redis()
        if selected_source == "mongo":
            logger.debug("Leyendo perfiles desde Mongo")
            return await self._read_profiles_from_mongo()
        logger.error(f"Fuente de perfiles no soportada: {selected_source}")
        raise ValueError(f"Fuente de perfiles no soportada: {selected_source}")

    async def load_profiles_to_mongo(self) -> int:
        logger.info(f"Iniciando carga de perfiles a Mongo en colección '{self._settings.mongo_profiles_collection}'")
        profiles = self._read_profile_index_jsonl()
        logger.debug(f"Se leyeron {len(profiles)} perfiles del archivo JSONL para Mongo")
        for idx, profile in enumerate(profiles):
            patient_key = str(profile.get("patient_key") or f"unknown-{idx}")
            document = {
                "patient_key": patient_key,
                "profile": profile,
            }
            await self.mongo_collection.replace_one(
                {"patient_key": patient_key},
                document,
                upsert=True,
            )
            if (idx + 1) % 50 == 0:
                logger.debug(f"Insertados {idx + 1}/{len(profiles)} documentos en Mongo")
        logger.info(f"✓ Cargados {len(profiles)} perfiles a Mongo exitosamente")
        return len(profiles)

    async def get_storage_status(self, sample_size: int = 5) -> dict[str, Any]:
        logger.debug(f"Consultando estado de almacenamiento de perfiles (sample_size={sample_size})")
        source_records = self._read_profile_index_jsonl()
        source_keys = [str(item.get("patient_key", "unknown")) for item in source_records[:sample_size]]
        logger.debug(f"Archivo fuente: {len(source_records)} perfiles, muestra: {source_keys}")

        redis_raw = await self.redis_client.get(self.PROFILE_INDEX_KEY)
        redis_count = 0
        redis_keys: list[str] = []
        if redis_raw:
            redis_profiles = json.loads(redis_raw)
            if isinstance(redis_profiles, list):
                redis_count = len(redis_profiles)
                redis_keys = [str(item.get("patient_key", "unknown")) for item in redis_profiles[:sample_size]]
        logger.debug(f"Redis: {redis_count} perfiles, muestra: {redis_keys}")

        mongo_count = await self.mongo_collection.count_documents({})
        mongo_docs = await self.mongo_collection.find({}, {"patient_key": 1, "_id": 0}).limit(sample_size).to_list(length=sample_size)
        mongo_keys = [str(doc.get("patient_key", "unknown")) for doc in mongo_docs]
        logger.debug(f"Mongo: {mongo_count} perfiles, muestra: {mongo_keys}")

        return {
            "profiles_dir": str(self._profiles_dir),
            "index_file": str(self._index_jsonl),
            "source_count": len(source_records),
            "source_sample_keys": source_keys,
            "redis_key": self.PROFILE_INDEX_KEY,
            "redis_count": redis_count,
            "redis_sample_keys": redis_keys,
            "mongo_collection": self._settings.mongo_profiles_collection,
            "mongo_count": mongo_count,
            "mongo_sample_keys": mongo_keys,
            "default_profile_source": self.default_source,
        }

    async def _read_profiles_from_redis(self) -> list[dict[str, Any]]:
        logger.debug(f"Intentando leer perfiles de Redis (clave: {self.PROFILE_INDEX_KEY})")
        raw = await self.redis_client.get(self.PROFILE_INDEX_KEY)
        if raw is None:
            logger.warning("Perfiles no encontrados en Redis, iniciando carga desde archivo")
            await self.load_profiles_to_redis()
            raw = await self.redis_client.get(self.PROFILE_INDEX_KEY)

        if raw is None:
            logger.error("No fue posible cargar perfiles de normalizacion desde Redis")
            raise ValueError("No fue posible cargar perfiles de normalizacion desde Redis")

        profiles = json.loads(raw)
        if not isinstance(profiles, list) or not profiles:
            logger.error("Datos de perfiles en Redis son inválidos o vacíos")
            raise ValueError("No hay perfiles de normalizacion disponibles en Redis")
        logger.debug(f"✓ Leyeron {len(profiles)} perfiles desde Redis")
        return profiles

    async def _read_profiles_from_mongo(self) -> list[dict[str, Any]]:
        logger.debug(f"Intentando leer perfiles de Mongo (colección: {self._settings.mongo_profiles_collection})")
        docs = await self.mongo_collection.find({}).to_list(length=None)
        if not docs:
            logger.warning("Colección Mongo vacía, iniciando carga desde archivo")
            await self.load_profiles_to_mongo()
            docs = await self.mongo_collection.find({}).to_list(length=None)

        profiles = [doc.get("profile") for doc in docs if isinstance(doc.get("profile"), dict)]
        if not profiles:
            logger.error("Documentos en Mongo no contienen datos de perfiles válidos")
            raise ValueError("No hay perfiles de normalizacion disponibles en Mongo")
        logger.debug(f"✓ Leyeron {len(profiles)} perfiles desde Mongo")
        return profiles

    def _read_profile_index_jsonl(self) -> list[dict[str, Any]]:
        logger.debug(f"Leyendo índice de perfiles desde {self._index_jsonl}")
        if not self._index_jsonl.exists():
            logger.error(f"Archivo de índice no encontrado: {self._index_jsonl}")
            raise FileNotFoundError(f"No se encontro index de perfiles: {self._index_jsonl}")

        records: list[dict[str, Any]] = []
        with self._index_jsonl.open("r", encoding="utf-8") as fp:
            for raw_line in fp:
                line = raw_line.strip()
                if not line:
                    continue
                records.append(json.loads(line))

        if not records:
            logger.error("El archivo de índice de perfiles está vacío")
            raise ValueError("El index de perfiles esta vacio")
        logger.debug(f"✓ Leyeron {len(records)} registros del archivo JSONL")
        return records
