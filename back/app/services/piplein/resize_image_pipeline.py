from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from app.services.pipeline_processor import PipelineProcessor
from app.services.piplein.types import NormalizationPipelineContext


class ResizeImagePipeline(PipelineProcessor[np.ndarray, NormalizationPipelineContext]):
    name = "1-resize-image"

    async def handle(
        self,
        payload: np.ndarray,
        context: NormalizationPipelineContext,
    ) -> np.ndarray:
        profile = context.closest_profile
        target_long_side = int(profile.get("target_long_side") or 1024)
        p_low = float(profile.get("normalization_p_low") or 1.0)
        p_high = float(profile.get("normalization_p_high") or 99.0)

        resized, resize_meta = self._resize_long_side(payload, target_long_side)
        normalized = self._robust_mad_normalize(resized, p_low=p_low, p_high=p_high)

        target_after_mean = self._safe_float(profile.get("after_mean"))
        target_after_std = self._safe_float(profile.get("after_std"))
        adjusted = self._match_target_stats(normalized, target_after_mean, target_after_std)

        context.applied_steps.append(self.name)
        context.runtime_metadata[self.name] = {
            "target_long_side": target_long_side,
            "p_low": p_low,
            "p_high": p_high,
            "output_shape": [int(adjusted.shape[0]), int(adjusted.shape[1])],
            **resize_meta,
        }
        return adjusted

    @staticmethod
    def _safe_float(value: Any, fallback: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _resize_long_side(image: np.ndarray, target_long_side: int) -> tuple[np.ndarray, dict[str, Any]]:
        h, w = image.shape[:2]
        if h <= 0 or w <= 0:
            raise ValueError("Imagen invalida para resize")

        scale = float(target_long_side) / float(max(h, w))
        new_h = max(1, int(round(h * scale)))
        new_w = max(1, int(round(w * scale)))

        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        resized = cv2.resize(image, (new_w, new_h), interpolation=interpolation)

        metadata = {
            "original_shape": [int(h), int(w)],
            "resized_shape": [int(new_h), int(new_w)],
            "scale_x": float(scale),
            "scale_y": float(scale),
        }
        return resized, metadata

    @staticmethod
    def _robust_mad_normalize(
        image: np.ndarray,
        p_low: float = 1.0,
        p_high: float = 99.0,
    ) -> np.ndarray:
        img = image.astype(np.float32)
        low = float(np.percentile(img, p_low))
        high = float(np.percentile(img, p_high))
        img_clip = np.clip(img, low, high)

        median = float(np.median(img_clip))
        mad = float(np.median(np.abs(img_clip - median)))

        if mad < 1e-8:
            base = (img_clip - low) / max(high - low, 1e-8)
        else:
            robust_z = (img_clip - median) / (1.4826 * mad + 1e-8)
            robust_z = np.clip(robust_z, -4.0, 4.0)
            base = (robust_z + 4.0) / 8.0

        normalized = np.nan_to_num(base * 255.0, nan=0.0, posinf=255.0, neginf=0.0)
        return np.clip(normalized, 0, 255).astype(np.uint8)

    @staticmethod
    def _match_target_stats(
        image_uint8: np.ndarray,
        target_mean: float,
        target_std: float,
    ) -> np.ndarray:
        img = image_uint8.astype(np.float32)
        current_mean = float(np.mean(img))
        current_std = float(np.std(img))

        if target_std <= 0 or current_std < 1e-8:
            return image_uint8

        adjusted = ((img - current_mean) * (target_std / current_std)) + target_mean
        adjusted = np.nan_to_num(adjusted, nan=0.0, posinf=255.0, neginf=0.0)
        return np.clip(adjusted, 0, 255).astype(np.uint8)
