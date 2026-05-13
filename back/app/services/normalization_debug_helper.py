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
) -> dict[str, Any]:
    container = get_container()
    service = container.normalization_service()
    return await service.normalize_file_paths(
        image_path=image_path,
        profile_source=profile_source,
        compare_image_path=compare_image_path,
        compare_profile_json_path=compare_profile_json_path,
    )


def decode_base64_image(image_base64: str) -> np.ndarray:
    raw = base64.b64decode(image_base64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("No fue posible decodificar la imagen base64")
    return image
