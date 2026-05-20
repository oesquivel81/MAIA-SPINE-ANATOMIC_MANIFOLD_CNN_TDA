from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.components.mongo_client import MongoComponent
from app.components.redis_client import RedisComponent
from app.components.s3_client import S3Component
from app.core.config import Settings
from pipeline_ml.normalization_stage.logger import log_method_start

logger = logging.getLogger(__name__)


@dataclass
class TraceIdentity:
    trace_id: str
    folder_name: str
    timestamp: str


class NormalizationTraceabilityService:
    def __init__(
        self,
        settings: Settings,
        redis_component: RedisComponent,
        mongo_component: MongoComponent,
        s3_component: S3Component | None = None,
    ):
        self._settings = settings
        self._redis = redis_component
        self._mongo = mongo_component
        self._s3 = s3_component
        self._base_dir = (
            Path(__file__).resolve().parents[2]
            / settings.normalization_traceability_output_dir
        )

    def build_identity(
        self,
        patient_name: str | None,
        patient_lastname: str | None,
        sex: str | None,
        age: int | None,
        weight: float | None,
        timestamp: str | None = None,
    ) -> TraceIdentity:
        log_method_start(logger, self.__class__.__name__, "build_identity")

        ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")

        safe_name = self._safe_token(patient_name, fallback="noname")
        safe_lastname = self._safe_token(patient_lastname, fallback="nolastname")
        safe_sex = self._safe_token(sex, fallback="na")
        safe_age = self._safe_token(age, fallback="0")
        safe_weight = self._safe_token(weight, fallback="0")

        folder_name = f"{safe_name}{safe_lastname}{safe_sex}{safe_weight}_{ts}"
        trace_id = f"{safe_name}{safe_sex}{safe_age}{safe_weight}_{ts}"

        return TraceIdentity(trace_id=trace_id, folder_name=folder_name, timestamp=ts)

    async def persist_trace(
        self,
        identity: TraceIdentity,
        payload: dict[str, Any],
        save_json: bool,
        normalized_image: np.ndarray | None = None,
        visualization_image: np.ndarray | None = None,
        generate_visualization: bool = True,
    ) -> dict[str, Any]:
        log_method_start(
            logger,
            self.__class__.__name__,
            "persist_trace",
            trace_id=identity.trace_id,
            save_json=save_json,
        )

        trace_document = {
            "trace_id": identity.trace_id,
            "folder_name": identity.folder_name,
            "timestamp": identity.timestamp,
            **payload,
        }

        result = {
            "trace_id": identity.trace_id,
            "trace_folder": identity.folder_name,
            "trace_timestamp": identity.timestamp,
            "trace_artifacts_dir": str(trace_dir),
            "trace_artifacts_uri": str(trace_dir),
            "next_stage_path": str(trace_dir),
            "trace_manifest_json_path": None,
            "trace_json_path": None,
            "trace_csv_path": None,
            "trace_normalized_image_path": None,
            "trace_visualization_path": None,
            "trace_redis_key": None,
            "trace_mongo_collection": None,
            "trace_route_b_mode": None,
            "trace_warnings": [],
        }

        trace_dir = self._base_dir / identity.folder_name
        if normalized_image is not None:
            image_dir = trace_dir / "normalized_image"
            image_dir.mkdir(parents=True, exist_ok=True)
            image_path = image_dir / f"{identity.trace_id}_normalized.png"
            ok = cv2.imwrite(str(image_path), normalized_image)
            if ok:
                result["trace_normalized_image_path"] = str(image_path)
                trace_document["trace_normalized_image_path"] = str(image_path)
            else:
                warning = "No se pudo guardar la imagen normalizada en normalized_image"
                logger.warning(warning)
                result["trace_warnings"].append(warning)

        if generate_visualization and visualization_image is not None:
            vis_dir = trace_dir / "visualization"
            vis_dir.mkdir(parents=True, exist_ok=True)
            vis_path = vis_dir / f"{identity.trace_id}_visualization.png"
            ok_vis = cv2.imwrite(str(vis_path), visualization_image)
            if ok_vis:
                result["trace_visualization_path"] = str(vis_path)
                trace_document["trace_visualization_path"] = str(vis_path)
            else:
                warning = "No se pudo guardar visualizacion en subdirectorio visualization"
                logger.warning(warning)
                result["trace_warnings"].append(warning)

        if self._settings.normalization_trace_route_b_enabled:
            route_b_mode = self._resolve_route_b_mode(save_json)
            route_b = self._persist_route_b(identity, trace_document, route_b_mode)
            result["trace_json_path"] = route_b.get("trace_json_path")
            result["trace_csv_path"] = route_b.get("trace_csv_path")
            result["trace_route_b_mode"] = route_b_mode
            if route_b.get("trace_json_path"):
                trace_document["trace_json_path"] = route_b["trace_json_path"]

        manifest_path = trace_dir / f"{identity.trace_id}_trace_manifest.json"
        manifest_path.write_text(
            json.dumps(trace_document, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        result["trace_manifest_json_path"] = str(manifest_path)

        if self._settings.normalization_trace_redis_enabled:
            redis_key = f"{self._settings.redis_normalization_trace_prefix}:{identity.trace_id}"
            try:
                await self._redis.client.set(redis_key, json.dumps(trace_document, ensure_ascii=False))
                result["trace_redis_key"] = redis_key
            except Exception as exc:
                warning = f"Redis opcional no disponible: {exc}"
                logger.warning(warning)
                result["trace_warnings"].append(warning)

        if self._settings.normalization_trace_mongo_enabled:
            try:
                mongo_collection = self._mongo.collection_by_name(
                    self._settings.mongo_normalization_traces_collection,
                )
                await mongo_collection.replace_one(
                    {"trace_id": identity.trace_id},
                    trace_document,
                    upsert=True,
                )
                result["trace_mongo_collection"] = self._settings.mongo_normalization_traces_collection
            except Exception as exc:
                warning = f"Mongo opcional no disponible: {exc}"
                logger.warning(warning)
                result["trace_warnings"].append(warning)

        if self._settings.normalization_trace_s3_enabled and self._s3 is not None:
            try:
                s3_uri = self._upload_trace_dir_to_s3(trace_dir=trace_dir, folder_name=identity.folder_name)
                result["trace_artifacts_uri"] = s3_uri
                result["next_stage_path"] = s3_uri
            except Exception as exc:
                warning = f"S3 opcional no disponible: {exc}"
                logger.warning(warning)
                result["trace_warnings"].append(warning)

        return result

    def _upload_trace_dir_to_s3(self, trace_dir: Path, folder_name: str) -> str:
        self._s3.ensure_bucket()
        bucket = self._settings.aws_s3_bucket
        prefix = self._settings.normalization_trace_s3_prefix.strip("/")

        for local_path in trace_dir.rglob("*"):
            if not local_path.is_file():
                continue
            relative = local_path.relative_to(trace_dir).as_posix()
            key = f"{prefix}/{folder_name}/{relative}" if prefix else f"{folder_name}/{relative}"
            self._s3.client.upload_file(str(local_path), bucket, key)

        if prefix:
            return f"s3://{bucket}/{prefix}/{folder_name}/"
        return f"s3://{bucket}/{folder_name}/"

    def _persist_route_b(
        self,
        identity: TraceIdentity,
        trace_document: dict[str, Any],
        route_b_mode: str,
    ) -> dict[str, str | None]:
        trace_dir = self._base_dir / identity.folder_name
        trace_dir.mkdir(parents=True, exist_ok=True)

        out: dict[str, str | None] = {
            "trace_json_path": None,
            "trace_csv_path": None,
        }

        if route_b_mode in {"json", "both"}:
            json_path = trace_dir / f"{identity.trace_id}.json"
            json_path.write_text(
                json.dumps(trace_document, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            out["trace_json_path"] = str(json_path)

        if route_b_mode in {"csv", "both"}:
            csv_path = self._base_dir / "normalization_traceability_index.csv"
            row = {
                "trace_id": identity.trace_id,
                "folder_name": identity.folder_name,
                "timestamp": identity.timestamp,
                "profile_source": trace_document.get("profile_source"),
                "closest_profile_key": trace_document.get("closest_profile_key"),
                "closest_profile_distance": trace_document.get("closest_profile_distance"),
                "trace_patient_name": trace_document.get("trace_patient_name"),
                "trace_patient_lastname": trace_document.get("trace_patient_lastname"),
                "trace_sex": trace_document.get("trace_sex"),
                "trace_age": trace_document.get("trace_age"),
                "trace_weight": trace_document.get("trace_weight"),
            }

            write_header = not csv_path.exists()
            with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=list(row.keys()))
                if write_header:
                    writer.writeheader()
                writer.writerow(row)

            out["trace_csv_path"] = str(csv_path)

        return out

    def _resolve_route_b_mode(self, save_json: bool) -> str:
        mode = (self._settings.normalization_trace_route_b_format or "auto").strip().lower()
        if mode in {"json", "csv", "both"}:
            return mode
        return "json" if save_json else "csv"

    @staticmethod
    def _safe_token(value: Any, fallback: str) -> str:
        if value is None:
            return fallback
        token = str(value).strip().lower()
        token = re.sub(r"[^a-z0-9]+", "", token)
        return token or fallback
