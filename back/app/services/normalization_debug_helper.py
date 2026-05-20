from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.container import get_container


async def debug_normalize_from_paths(
    image_path: str | Path,
    profile_source: str | None = None,
    compare_image_path: str | Path | None = None,
    compare_profile_json_path: str | Path | None = None,
    trace_patient_name: str | None = None,
    trace_patient_lastname: str | None = None,
    trace_sex: str | None = None,
    trace_age: int | None = None,
    trace_weight: float | None = None,
    trace_timestamp: str | None = None,
    debug_save_json: bool | None = None,
    trace_generate_visualization: bool | None = None,
) -> dict[str, Any]:
    container = get_container()
    service = container.normalization_service()
    return await service.normalize_file_paths(
        image_path=image_path,
        profile_source=profile_source,
        compare_image_path=compare_image_path,
        compare_profile_json_path=compare_profile_json_path,
        trace_patient_name=trace_patient_name,
        trace_patient_lastname=trace_patient_lastname,
        trace_sex=trace_sex,
        trace_age=trace_age,
        trace_weight=trace_weight,
        trace_timestamp=trace_timestamp,
        debug_save_json=debug_save_json,
        trace_generate_visualization=trace_generate_visualization,
    )


def decode_base64_image(image_base64: str) -> np.ndarray:
    raw = base64.b64decode(image_base64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("No fue posible decodificar la imagen base64")
    return image
