from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.components.redis_client import RedisComponent
from app.core.config import Settings
from redis.asyncio import Redis


class NormalizationProfileLoader:
    PROFILE_INDEX_KEY = "normalization_profiles:index:v1"
    PROFILE_COUNT_KEY = "normalization_profiles:count:v1"

    def __init__(self, settings: Settings, redis_component: RedisComponent):
        self._settings = settings
        self._redis = redis_component
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
    def default_source(self) -> str:
        return self._settings.normalization_profile_source.lower()

    async def load_profiles_to_redis(self) -> int:
        profiles = self._read_profile_index_jsonl()
        await self.redis_client.set(self.PROFILE_INDEX_KEY, json.dumps(profiles))
        await self.redis_client.set(self.PROFILE_COUNT_KEY, len(profiles))
        return len(profiles)

    async def get_profiles(self, source: str | None = None) -> list[dict[str, Any]]:
        selected_source = (source or self.default_source).lower()
        if selected_source == "json":
            return self._read_profile_index_jsonl()
        if selected_source == "redis":
            return await self._read_profiles_from_redis()
        raise ValueError(f"Fuente de perfiles no soportada: {selected_source}")

    async def _read_profiles_from_redis(self) -> list[dict[str, Any]]:
        raw = await self.redis_client.get(self.PROFILE_INDEX_KEY)
        if raw is None:
            await self.load_profiles_to_redis()
            raw = await self.redis_client.get(self.PROFILE_INDEX_KEY)

        if raw is None:
            raise ValueError("No fue posible cargar perfiles de normalizacion desde Redis")

        profiles = json.loads(raw)
        if not isinstance(profiles, list) or not profiles:
            raise ValueError("No hay perfiles de normalizacion disponibles en Redis")
        return profiles

    def _read_profile_index_jsonl(self) -> list[dict[str, Any]]:
        if not self._index_jsonl.exists():
            raise FileNotFoundError(f"No se encontro index de perfiles: {self._index_jsonl}")

        records: list[dict[str, Any]] = []
        with self._index_jsonl.open("r", encoding="utf-8") as fp:
            for raw_line in fp:
                line = raw_line.strip()
                if not line:
                    continue
                records.append(json.loads(line))

        if not records:
            raise ValueError("El index de perfiles esta vacio")
        return records
