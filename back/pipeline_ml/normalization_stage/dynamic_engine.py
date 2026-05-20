from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.services.piplein import (
    NormalizationPipelineContext,
    build_ordered_pipeline,
    wire_pipeline_chain,
)
from pipeline_ml.normalization_stage.logger import log_method_start

logger = logging.getLogger(__name__)


class DynamicNormalizationEngine:
    """Motor de normalizacion dinamica inspirado en el flujo de Colab.

    Selecciona el perfil mas cercano por estadisticas y ejecuta la cadena
    de normalizacion configurada.
    """

    def select_closest_profile(
        self,
        input_stats: dict[str, float],
        profiles: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], float]:
        log_method_start(
            logger,
            self.__class__.__name__,
            "select_closest_profile",
            profiles=len(profiles),
        )

        if not profiles:
            raise ValueError("No hay perfiles para seleccionar")

        weights = {
            "before_mean": 1.0,
            "before_std": 1.0,
            "before_median": 0.7,
            "before_p5": 0.5,
            "before_p95": 0.5,
            "aspect_ratio": 1.2,
        }
        metric_map = {
            "before_mean": input_stats["mean"],
            "before_std": input_stats["std"],
            "before_median": input_stats["median"],
            "before_p5": input_stats["p5"],
            "before_p95": input_stats["p95"],
            "aspect_ratio": input_stats["aspect_ratio"],
        }

        best_profile = profiles[0]
        best_distance = float("inf")

        for profile in profiles:
            distance = 0.0
            for field, input_value in metric_map.items():
                profile_value = self._safe_float(profile.get(field), input_value)
                norm = max(abs(profile_value), 1.0)
                distance += weights[field] * (abs(input_value - profile_value) / norm)

            if distance < best_distance:
                best_distance = distance
                best_profile = profile

        return best_profile, float(best_distance)

    async def run(
        self,
        image: np.ndarray,
        closest_profile: dict[str, Any],
        distance: float,
    ) -> tuple[np.ndarray, dict[str, Any], NormalizationPipelineContext]:
        log_method_start(
            logger,
            self.__class__.__name__,
            "run",
            image_shape=list(image.shape),
            patient_key=closest_profile.get("patient_key"),
        )

        ordered_map = build_ordered_pipeline()
        chain_head = wire_pipeline_chain(ordered_map)
        context = NormalizationPipelineContext(
            closest_profile=closest_profile,
            closest_profile_distance=distance,
        )
        normalized = await chain_head.process(image, context)
        return normalized, ordered_map, context

    @staticmethod
    def _safe_float(value: Any, fallback: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
