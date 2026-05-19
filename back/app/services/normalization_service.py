from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile

from app.services.normalization_profile_loader import NormalizationProfileLoader
from app.services.piplein import (
    NormalizationPipelineContext,
    build_ordered_pipeline,
    wire_pipeline_chain,
)


class NormalizationService:
    def __init__(self, profile_loader: NormalizationProfileLoader):
        self._profile_loader = profile_loader
        
    async def normalize_bytes(
        self,
        content: bytes,
        profile_source: str | None = None,
        compare_content: bytes | None = None,
        compare_profile_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        image = self._decode_grayscale(content)
        return await self._normalize_array(
            image=image,
            profile_source=profile_source,
            compare_image=self._decode_grayscale(compare_content) if compare_content is not None else None,
            compare_profile_payload=compare_profile_payload,
        )
    
    async def normalize_file_paths(
        self,
        image_path: str | Path,
        profile_source: str | None = None,
        compare_image_path: str | Path | None = None,
        compare_profile_json_path: str | Path | None = None,
    ) -> dict[str, Any]:
        image_bytes = Path(image_path).read_bytes()
        compare_bytes = None
        compare_profile_payload = None

        if compare_image_path is not None:
            compare_bytes = Path(compare_image_path).read_bytes()

        if compare_profile_json_path is not None:
            compare_profile_payload = json.loads(Path(compare_profile_json_path).read_text(encoding="utf-8"))

        return await self.normalize_bytes(
            content=image_bytes,
            profile_source=profile_source,
            compare_content=compare_bytes,
            compare_profile_payload=compare_profile_payload,
        )

    def visualize_normalization(
        self,
        original: np.ndarray,
        normalized: np.ndarray,
        compare_normalized: np.ndarray | None = None,
    ) -> np.ndarray:
        return self._build_visualization(original, normalized, compare_normalized)

    async def normalize_image(
        self,
        file: UploadFile,
        profile_source: str | None = None,
        compare_file: UploadFile | None = None,
        compare_profile_json: UploadFile | None = None,
    ) -> dict[str, Any]:
        raw = await file.read()
        compare_raw = await compare_file.read() if compare_file is not None else None
        compare_profile_payload = (
            await self._decode_json_upload(compare_profile_json)
            if compare_profile_json is not None
            else None
        )
        return await self.normalize_bytes(
            content=raw,
            profile_source=profile_source,
            compare_content=compare_raw,
            compare_profile_payload=compare_profile_payload,
        )

    async def _normalize_array(
        self,
        image: np.ndarray,
        profile_source: str | None = None,
        compare_image: np.ndarray | None = None,
        compare_profile_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        input_stats = self._compute_stats(image)

        selected_profile_source = (profile_source or self._profile_loader.default_source).lower()
        profiles = await self._get_profiles(selected_profile_source)
        closest_profile, distance = self._find_closest_profile(input_stats, profiles)

        normalized, ordered_map, context = await self._run_pipeline(image, closest_profile, distance)
        output_stats = self._compute_stats(normalized)
        output_base64 = self._encode_png_base64(normalized)

        comparison = await self._build_comparison_payload_from_arrays(
            base_image=image,
            base_output=normalized,
            compare_image=compare_image,
            compare_profile_payload=compare_profile_payload,
            profiles=profiles,
        )

        analysis = self._build_analysis_payload(
            normalized=normalized,
            output_stats=output_stats,
            output_shape=[int(normalized.shape[0]), int(normalized.shape[1])],
        )

        return {
            "success": True,
            "profile_source": selected_profile_source,
            "implementation_map": list(ordered_map.keys()),
            "closest_profile_key": str(closest_profile.get("patient_key", "unknown")),
            "closest_profile_distance": float(distance),
            "closest_profile_summary": {
                "patient_key": closest_profile.get("patient_key"),
                "normalization_mode": closest_profile.get("normalization_mode"),
                "normalization_p_low": closest_profile.get("normalization_p_low"),
                "normalization_p_high": closest_profile.get("normalization_p_high"),
                "target_long_side": closest_profile.get("target_long_side"),
                "aspect_ratio": closest_profile.get("aspect_ratio"),
            },
            "input_stats": input_stats,
            "output_stats": output_stats,
            "output_shape": [int(normalized.shape[0]), int(normalized.shape[1])],
            "output_image_base64": output_base64,
            "output_image_url": f"data:image/png;base64,{output_base64}",
            "runtime_metadata": context.runtime_metadata,
            "analysis": analysis,
            "comparison": comparison,
        }

    async def _get_profiles(self, profile_source: str) -> list[dict[str, Any]]:
        try:
            return await self._profile_loader.get_profiles(profile_source)
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    async def _run_pipeline(
        self,
        image: np.ndarray,
        closest_profile: dict[str, Any],
        distance: float,
    ) -> tuple[np.ndarray, dict[str, Any], NormalizationPipelineContext]:
        ordered_map = build_ordered_pipeline()
        chain_head = wire_pipeline_chain(ordered_map)
        context = NormalizationPipelineContext(
            closest_profile=closest_profile,
            closest_profile_distance=distance,
        )
        normalized = await chain_head.process(image, context)
        return normalized, ordered_map, context

    async def _build_comparison_payload(
        self,
        base_image: np.ndarray,
        base_output: np.ndarray,
        profile_source: str,
        compare_file: UploadFile | None,
        compare_profile_json: UploadFile | None,
        profiles: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if compare_file is None:
            return None

        compare_raw = await compare_file.read()
        compare_image = self._decode_grayscale(compare_raw)
        compare_input_stats = self._compute_stats(compare_image)

        compare_profile_payload: dict[str, Any] | None = None
        compare_profile_source = "nearest_profile"
        compare_distance = 0.0

        if compare_profile_json is not None:
            compare_profile_payload = await self._decode_json_upload(compare_profile_json)
            compare_profile = self._profile_from_runtime_json(compare_profile_payload)
            compare_profile_source = "uploaded_json"
        else:
            compare_profile, compare_distance = self._find_closest_profile(compare_input_stats, profiles)
            compare_profile_payload = compare_profile

        compare_output, _, _ = await self._run_pipeline(
            compare_image,
            compare_profile,
            compare_distance,
        )
        compare_output_stats = self._compute_stats(compare_output)

        compare_output_base64 = self._encode_png_base64(compare_output)
        comparison_visualization_base64 = self._encode_png_base64(
            self._build_visualization(base_image, base_output, compare_output),
        )
        return {
            "compare_profile_source": compare_profile_source,
            "compare_profile_summary": {
                "patient_key": compare_profile.get("patient_key"),
                "normalization_mode": compare_profile.get("normalization_mode"),
                "normalization_p_low": compare_profile.get("normalization_p_low"),
                "normalization_p_high": compare_profile.get("normalization_p_high"),
                "target_long_side": compare_profile.get("target_long_side"),
                "aspect_ratio": compare_profile.get("aspect_ratio"),
            },
            "compare_input_stats": compare_input_stats,
            "compare_output_stats": compare_output_stats,
            "compare_output_shape": [int(compare_output.shape[0]), int(compare_output.shape[1])],
            "compare_output_image_base64": compare_output_base64,
            "compare_output_image_url": f"data:image/png;base64,{compare_output_base64}",
            "comparison_visualization_base64": comparison_visualization_base64,
            "comparison_visualization_url": f"data:image/png;base64,{comparison_visualization_base64}",
            "compare_profile_payload": self._sanitize_json_payload(compare_profile_payload),
        }

    async def _build_comparison_payload_from_arrays(
        self,
        base_image: np.ndarray,
        base_output: np.ndarray,
        compare_image: np.ndarray | None,
        compare_profile_payload: dict[str, Any] | None,
        profiles: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if compare_image is None:
            return None

        compare_input_stats = self._compute_stats(compare_image)
        compare_profile_source = "nearest_profile"
        compare_distance = 0.0

        if compare_profile_payload is not None:
            compare_profile = self._profile_from_runtime_json(compare_profile_payload)
            compare_profile_source = "uploaded_json"
        else:
            compare_profile, compare_distance = self._find_closest_profile(compare_input_stats, profiles)
            compare_profile_payload = compare_profile

        compare_output, _, _ = await self._run_pipeline(
            compare_image,
            compare_profile,
            compare_distance,
        )
        compare_output_stats = self._compute_stats(compare_output)
        compare_output_base64 = self._encode_png_base64(compare_output)
        comparison_visualization_base64 = self._encode_png_base64(
            self.visualize_normalization(base_image, base_output, compare_output),
        )

        return {
            "compare_profile_source": compare_profile_source,
            "compare_profile_summary": {
                "patient_key": compare_profile.get("patient_key"),
                "normalization_mode": compare_profile.get("normalization_mode"),
                "normalization_p_low": compare_profile.get("normalization_p_low"),
                "normalization_p_high": compare_profile.get("normalization_p_high"),
                "target_long_side": compare_profile.get("target_long_side"),
                "aspect_ratio": compare_profile.get("aspect_ratio"),
            },
            "compare_input_stats": compare_input_stats,
            "compare_output_stats": compare_output_stats,
            "compare_output_shape": [int(compare_output.shape[0]), int(compare_output.shape[1])],
            "compare_output_image_base64": compare_output_base64,
            "compare_output_image_url": f"data:image/png;base64,{compare_output_base64}",
            "comparison_visualization_base64": comparison_visualization_base64,
            "comparison_visualization_url": f"data:image/png;base64,{comparison_visualization_base64}",
            "compare_profile_payload": self._sanitize_json_payload(compare_profile_payload),
        }
    @staticmethod
    async def _decode_json_upload(file: UploadFile) -> dict[str, Any]:
        raw = await file.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="JSON de comparacion invalido") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="El JSON de comparacion debe ser un objeto")
        return payload

    def _profile_from_runtime_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        before = payload.get("image_before_norm_stats") or {}
        return {
            "patient_key": payload.get("patient_id") or payload.get("patient_key") or "uploaded-json",
            "normalization_mode": payload.get("normalization_mode", "robust_mad"),
            "normalization_p_low": payload.get("normalization_p_low", 1.0),
            "normalization_p_high": payload.get("normalization_p_high", 99.0),
            "target_long_side": payload.get("target_long_side", 1024),
            "aspect_ratio": self._extract_aspect_ratio(payload),
            "after_mean": self._safe_float((payload.get("image_after_norm_stats") or {}).get("mean"), 0.0),
            "after_std": self._safe_float((payload.get("image_after_norm_stats") or {}).get("std"), 1.0),
            "before_mean": self._safe_float(before.get("mean"), 0.0),
            "before_std": self._safe_float(before.get("std"), 1.0),
            "before_median": self._safe_float(before.get("median"), 0.0),
            "before_p5": self._safe_float(before.get("p5"), 0.0),
            "before_p95": self._safe_float(before.get("p95"), 0.0),
        }

    @staticmethod
    def _extract_aspect_ratio(payload: dict[str, Any]) -> float:
        original_shape = payload.get("original_shape") or []
        if isinstance(original_shape, list) and len(original_shape) >= 2:
            h = float(original_shape[0])
            w = max(float(original_shape[1]), 1.0)
            return h / w
        return 1.0

    @staticmethod
    def _sanitize_json_payload(payload: dict[str, Any]) -> dict[str, Any]:
        allowed_scalar = (str, int, float, bool, type(None))
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, allowed_scalar):
                sanitized[key] = value
            elif isinstance(value, list):
                sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = value
            else:
                sanitized[key] = str(value)
        return sanitized

    @staticmethod
    def _decode_grayscale(content: bytes) -> np.ndarray:
        arr = np.frombuffer(content, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise HTTPException(status_code=400, detail="Imagen invalida o formato no soportado")
        return image

    @staticmethod
    def _compute_stats(image: np.ndarray) -> dict[str, float]:
        img = image.astype(np.float32)
        return {
            "mean": float(np.mean(img)),
            "std": float(np.std(img)),
            "median": float(np.median(img)),
            "p5": float(np.percentile(img, 5)),
            "p95": float(np.percentile(img, 95)),
            "min": float(np.min(img)),
            "max": float(np.max(img)),
            "aspect_ratio": float(img.shape[0] / max(img.shape[1], 1)),
        }

    def _build_analysis_payload(
        self,
        normalized: np.ndarray,
        output_stats: dict[str, float],
        output_shape: list[int],
    ) -> dict[str, Any]:
        curve = self._estimate_spine_curve(normalized)
        segmentation = self._estimate_segmentation(normalized, curve)

        return {
            "curve": curve,
            "segmentation": segmentation,
            "color_index": self._compute_color_index(normalized),
            "heatmap_data": self._build_heatmap_matrix(normalized),
            "measurements": self._build_measurements(curve, output_stats, output_shape),
        }

    def _estimate_spine_curve(self, image: np.ndarray) -> dict[str, Any]:
        image_uint8 = image.astype(np.uint8)
        blurred = cv2.GaussianBlur(image_uint8, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 120)

        rows = 16
        height, width = image_uint8.shape[:2]
        ys = np.linspace(0, height - 1, num=rows, dtype=int)
        positions: list[float] = []

        for y in ys:
            row_edges = np.where(edges[y] > 0)[0]
            if row_edges.size > 0:
                positions.append(float(np.mean(row_edges)))
                continue

            row_pixels = image_uint8[y]
            threshold = np.percentile(row_pixels, 80)
            row_candidates = np.where(row_pixels >= threshold)[0]
            if row_candidates.size > 0:
                positions.append(float(np.mean(row_candidates)))
            else:
                positions.append(float(width / 2))

        horizontal_shift = float(positions[-1] - positions[0]) if len(positions) >= 2 else 0.0
        max_offset = float(max(abs(np.array(positions) - (width / 2)))) if positions else 0.0
        slope = float(horizontal_shift / max(max(1, height - 1), 1))
        estimated_cobb_angle = float(min(max(abs(slope) * 80.0, 0.0), 60.0))
        direction = "dextroconvex" if slope > 0 else "levoconvex"
        severity = (
            "crítico" if estimated_cobb_angle >= 25.0 else
            "moderado" if estimated_cobb_angle >= 12.0 else
            "leve"
        )
        major_curve_span = "T8-L2" if abs(slope) >= 0.08 else "T3-T12"

        return {
            "detected": len(positions) >= 2,
            "direction": direction,
            "estimated_cobb_angle": round(estimated_cobb_angle, 1),
            "severity": severity,
            "major_curve_span": major_curve_span,
            "curve_points": [
                {"x": float(positions[index]), "y": float(y)}
                for index, y in enumerate(ys)
            ],
            "horizontal_shift": round(horizontal_shift, 2),
            "max_offset": round(max_offset, 2),
        }

    def _estimate_segmentation(self, image: np.ndarray, curve: dict[str, Any]) -> dict[str, Any]:
        height, width = image.shape[:2]
        highlighted = ["T8", "T9", "T10", "L1"] if curve.get("detected") else []
        curve_type = "Torácica" if "T" in curve.get("major_curve_span", "") else "Lumbar"

        return {
            "origin": "centroide",
            "centroid": {"x": round(float(width) / 2.0, 1), "y": round(float(height) / 2.0, 1)},
            "highlighted_vertebrae": highlighted,
            "curve_type": curve_type,
            "spine_center_line": curve.get("curve_points", []),
        }

    def _compute_color_index(self, image: np.ndarray) -> dict[str, Any]:
        image_uint8 = image.astype(np.uint8)
        histogram = cv2.calcHist([image_uint8], [0], None, [5], [0, 256]).flatten()
        total_pixels = float(np.sum(histogram)) or 1.0

        bands: list[dict[str, Any]] = []
        colors = ['#1e3a8a', '#3b82f6', '#10b981', '#fbbf24', '#ef4444']

        for index, value in enumerate(histogram):
            lower = int(index * 51.2)
            upper = int(min(255, (index + 1) * 51.2 - 1))
            bands.append({
                "range": f"{lower}-{upper}",
                "percentage": round((float(value) / total_pixels) * 100.0, 1),
                "color": colors[index],
                "count": int(value),
            })

        return {
            "average_intensity": round(float(np.mean(image_uint8)), 1),
            "median_intensity": round(float(np.median(image_uint8)), 1),
            "bands": bands,
        }

    def _build_heatmap_matrix(self, image: np.ndarray) -> list[list[float]]:
        rows, cols = 20, 12
        resized = cv2.resize(image.astype(np.uint8), (cols, rows), interpolation=cv2.INTER_AREA)
        return [
            [round(float(value) / 255.0, 3) for value in row]
            for row in resized
        ]

    def _build_measurements(
        self,
        curve: dict[str, Any],
        output_stats: dict[str, float],
        output_shape: list[int],
    ) -> list[dict[str, Any]]:
        angle = float(curve.get("estimated_cobb_angle", 0.0))
        aspect_ratio = float(output_stats.get("aspect_ratio", 1.0))
        std_value = float(output_stats.get("std", 0.0))

        cobb_status = "normal"
        if angle >= 25.0:
            cobb_status = "critical"
        elif angle >= 10.0:
            cobb_status = "warning"

        pelvic_tilt = round(min(max(aspect_ratio * 4.5, 4.0), 18.0), 1)
        pelvic_status = "normal" if 5.0 <= pelvic_tilt <= 10.0 else "warning"

        lordosis = round(min(max(35.0 + abs(angle) * 0.7, 20.0), 70.0), 1)
        lordosis_status = "normal" if 40.0 <= lordosis <= 60.0 else "warning"

        cifosis = round(min(max(25.0 + abs(angle) * 0.5, 15.0), 55.0), 1)
        cifosis_status = "normal" if 20.0 <= cifosis <= 45.0 else "warning"

        deviation = round(min(max(std_value * 0.25, 0.0), 20.0), 1)
        deviation_status = "normal" if deviation <= 5.0 else "warning" if deviation <= 12.0 else "critical"

        return [
            {
                "parameter": "Ángulo Cobb",
                "value": angle,
                "unit": "°",
                "normal_range": "< 10°",
                "status": cobb_status,
            },
            {
                "parameter": "Inclinación pélvica",
                "value": pelvic_tilt,
                "unit": "°",
                "normal_range": "5-10°",
                "status": pelvic_status,
            },
            {
                "parameter": "Lordosis lumbar",
                "value": lordosis,
                "unit": "°",
                "normal_range": "40-60°",
                "status": lordosis_status,
            },
            {
                "parameter": "Cifosis torácica",
                "value": cifosis,
                "unit": "°",
                "normal_range": "20-45°",
                "status": cifosis_status,
            },
            {
                "parameter": "Desviación lateral",
                "value": deviation,
                "unit": "mm",
                "normal_range": "< 5mm",
                "status": deviation_status,
            },
        ]
    @staticmethod
    def _safe_float(value: Any, fallback: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _find_closest_profile(
        self,
        input_stats: dict[str, float],
        profiles: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], float]:
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

    @staticmethod
    def _encode_png_base64(image: np.ndarray) -> str:
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise HTTPException(status_code=500, detail="No fue posible codificar la imagen de salida")
        return base64.b64encode(encoded.tobytes()).decode("utf-8")

    @staticmethod
    def _build_visualization(
        original: np.ndarray,
        normalized: np.ndarray,
        compare_normalized: np.ndarray | None = None,
    ) -> np.ndarray:
        if compare_normalized is None:
            compare_normalized = normalized

        target_height = max(original.shape[0], normalized.shape[0], compare_normalized.shape[0])
        original_panel = NormalizationService._resize_to_height(original, target_height)
        normalized_panel = NormalizationService._resize_to_height(normalized, target_height)
        compare_panel = NormalizationService._resize_to_height(compare_normalized, target_height)
        return np.hstack([original_panel, normalized_panel, compare_panel])

    @staticmethod
    def _resize_to_height(image: np.ndarray, target_height: int) -> np.ndarray:
        if image.shape[0] == target_height:
            return image
        scale = target_height / float(max(image.shape[0], 1))
        target_width = max(1, int(round(image.shape[1] * scale)))
        return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)
