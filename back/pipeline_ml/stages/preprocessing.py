from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.normalization_stage.dynamic_engine import DynamicNormalizationEngine
from pipeline_ml.stages.base import PipelineStage
from pipeline_ml.utils.stage_report import StageReport


class PreprocessingStage(PipelineStage):
    name = "preprocessing"

    def run(self, payload: dict[str, Any], context: PipelineContext, logger: PipelineLogger) -> dict[str, Any]:
        image: np.ndarray | None = payload.get("image")
        if image is None:
            raise ValueError("PreprocessingStage: no hay imagen en el payload")

        # --- 1. Cargar perfiles de normalización ---
        profiles = self._load_profiles(context, logger)
        logger.info(f"Preprocessing: {len(profiles)} perfiles de normalización cargados")

        # --- 2. Estadísticas de la imagen de entrada ---
        input_stats = self._compute_stats(image)
        logger.debug(f"Preprocessing: stats entrada → mean={input_stats['mean']:.2f}, std={input_stats['std']:.2f}")

        # --- 3. Seleccionar perfil más cercano y normalizar ---
        engine = DynamicNormalizationEngine()
        closest_profile, distance = engine.select_closest_profile(input_stats, profiles)
        logger.info(
            f"Preprocessing: perfil seleccionado={closest_profile.get('patient_key', '?')}, "
            f"distancia={distance:.6f}"
        )

        loop = asyncio.new_event_loop()
        try:
            normalized, _, norm_ctx = loop.run_until_complete(
                engine.run(image, closest_profile, distance)
            )
        finally:
            loop.close()

        # --- 4. Estadísticas de la imagen normalizada ---
        output_stats = self._compute_stats(normalized)
        logger.debug(f"Preprocessing: stats salida → mean={output_stats['mean']:.2f}, std={output_stats['std']:.2f}")

        # --- 5. Guardar imagen normalizada ---
        normalized_image_path = context.outputs_dir / "normalized_image.png"
        cv2.imwrite(str(normalized_image_path), normalized)
        logger.info(f"Preprocessing: imagen normalizada guardada en {normalized_image_path}")

        # --- 6. Construir trace JSON (formato N_1_normalization_profile.json) ---
        resize_meta = norm_ctx.runtime_metadata.get("1-resize-image", {})
        trace = {
            "normalization_mode": closest_profile.get("normalization_mode"),
            "normalization_p_low": closest_profile.get("normalization_p_low"),
            "normalization_p_high": closest_profile.get("normalization_p_high"),
            "target_long_side": closest_profile.get("target_long_side"),
            "standardize_long_side": bool(closest_profile.get("target_long_side")),
            "original_shape": resize_meta.get("original_shape"),
            "resized_shape": resize_meta.get("resized_shape"),
            "final_image_shape": [int(normalized.shape[0]), int(normalized.shape[1])],
            "scale_x": resize_meta.get("scale_x"),
            "scale_y": resize_meta.get("scale_y"),
            "closest_profile_key": str(closest_profile.get("patient_key", "unknown")),
            "closest_profile_distance": float(distance),
            "image_before_norm_stats": {k: v for k, v in input_stats.items() if k != "aspect_ratio"},
            "image_after_norm_stats": {k: v for k, v in output_stats.items() if k != "aspect_ratio"},
        }

        trace_json_path = context.outputs_dir / "normalization_trace.json"
        trace_json_path.write_text(json.dumps(trace, indent=2), encoding="utf-8")
        logger.info(f"Preprocessing: trace JSON guardado en {trace_json_path}")

        # --- 7. Actualizar payload ---
        payload["image"] = normalized
        payload["normalized_image_path"] = str(normalized_image_path)
        payload["normalization_trace"] = trace
        payload["normalization_trace_path"] = str(trace_json_path)
        payload["preprocessed"] = True

        return payload

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_profiles(context: PipelineContext, logger: PipelineLogger) -> list[dict]:
        """Localiza y carga el JSONL de perfiles de normalización.

        Orden de búsqueda:
        1. context.metadata["normalization_profile_jsonl"] (configurable via PipelinePaths)
        2. resource_paths del AssetBundle que terminen en .jsonl
        3. Fallback: cwd / resources / NORMALIZATION_PROFILES / normalization_profile_index.jsonl
        """
        candidates: list[Path] = []

        configured: str = context.metadata.get("normalization_profile_jsonl", "")
        if configured:
            candidates.append(Path(configured))

        for rp in context.assets.resource_paths:
            p = Path(rp)
            if p.suffix == ".jsonl":
                candidates.append(p)

        candidates.append(
            Path.cwd() / "resources" / "NORMALIZATION_PROFILES" / "normalization_profile_index.jsonl"
        )

        for candidate in candidates:
            if candidate.exists():
                logger.info(f"Preprocessing: leyendo perfiles desde {candidate}")
                lines = candidate.read_text(encoding="utf-8").splitlines()
                return [json.loads(line) for line in lines if line.strip()]

        raise FileNotFoundError(
            "PreprocessingStage: no se encontró el archivo JSONL de perfiles de normalización. "
            "Configura paths.normalization_profile_jsonl en PipelineConfig o inclúyelo en resource_paths."
        )

    @staticmethod
    def _compute_stats(image: np.ndarray) -> dict[str, float]:
        img = image.astype(np.float32)
        return {
            "min": float(np.min(img)),
            "max": float(np.max(img)),
            "mean": float(np.mean(img)),
            "std": float(np.std(img)),
            "median": float(np.median(img)),
            "p1": float(np.percentile(img, 1)),
            "p5": float(np.percentile(img, 5)),
            "p95": float(np.percentile(img, 95)),
            "p99": float(np.percentile(img, 99)),
            "aspect_ratio": float(img.shape[0] / max(img.shape[1], 1)),
        }

    def describe_output(self, payload: dict[str, Any]) -> StageReport:
        """Campos esperados tras preprocessing."""
        report = StageReport(stage_name=self.name)
        for key in ("image", "ingested", "preprocessed", "normalized_image_path", "normalization_trace_path"):
            report.add(key, payload.get(key, "<ausente>"))
        return report
