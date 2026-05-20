"""
Prueba local del fix en NormalizationTraceabilityService.persist_trace
Verifica que la imagen normalizada y el JSON se guardan correctamente.
NO requiere Redis, MongoDB ni S3.

Ejecucion desde back/:
    python scripts/test_traceability_local.py
    python scripts/test_traceability_local.py --image /ruta/a/imagen.jpg
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# --- path setup ------------------------------------------------------------
BACK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_DIR))

# Mockear modulos pesados ANTES de cualquier import del proyecto
# para evitar que fallen motor/redis/fastapi que no se necesitan aqui
_MOCKS = [
    "motor", "motor.motor_asyncio",
    "redis", "redis.asyncio",
    "fastapi", "fastapi.exceptions", "fastapi.responses",
    "botocore", "botocore.exceptions", "botocore.client",
    "boto3", "boto3.session",
]
for _mod in _MOCKS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
# ---------------------------------------------------------------------------

import numpy as np

from app.core.config import Settings
from pipeline_ml.normalization_stage.traceability import NormalizationTraceabilityService


def _make_stubs():
    """Stubs minimos para Redis y Mongo (no se usan con los flags en False)."""
    redis_stub = MagicMock()
    mongo_stub = MagicMock()
    return redis_stub, mongo_stub


def _make_settings(output_dir: str) -> Settings:
    return Settings(
        normalization_traceability_enabled=True,
        normalization_traceability_output_dir=output_dir,
        normalization_trace_redis_enabled=False,
        normalization_trace_mongo_enabled=False,
        normalization_trace_s3_enabled=False,
        normalization_trace_route_b_enabled=True,
        normalization_trace_route_b_format="json",
        normalization_trace_visualization_enabled=True,
    )


def _make_fake_image(h: int = 256, w: int = 128) -> np.ndarray:
    rng = np.random.default_rng(42)
    return (rng.integers(0, 256, size=(h, w), dtype=np.uint8))


async def run_test(image_path: str | None) -> None:
    output_dir = "docs/normalization_traceability_runtime"
    settings = _make_settings(output_dir)
    redis_stub, mongo_stub = _make_stubs()

    svc = NormalizationTraceabilityService(
        settings=settings,
        redis_component=redis_stub,
        mongo_component=mongo_stub,
        s3_component=None,
    )

    # --- imagen de prueba --------------------------------------------------
    if image_path:
        import cv2
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"[ERROR] No se pudo leer la imagen: {image_path}")
            sys.exit(1)
        print(f"[INFO] Usando imagen real: {image_path}  shape={img.shape}")
    else:
        img = _make_fake_image()
        print(f"[INFO] Usando imagen sintetica shape={img.shape}")

    vis = np.hstack([img, img])  # visualizacion simple: lado a lado

    # --- identidad del trace -----------------------------------------------
    identity = svc.build_identity(
        patient_name="Test",
        patient_lastname="Local",
        sex="M",
        age=25,
        weight=70.0,
    )
    print(f"[INFO] trace_id     = {identity.trace_id}")
    print(f"[INFO] folder_name  = {identity.folder_name}")

    # --- payload minimo ----------------------------------------------------
    payload: dict[str, Any] = {
        "profile_source": "json",
        "closest_profile_key": "test_profile",
        "closest_profile_distance": 0.123,
        "input_stats": {"mean": float(img.mean()), "std": float(img.std())},
        "output_stats": {"mean": float(img.mean()), "std": float(img.std())},
    }

    # --- llamar persist_trace (aqui estaba el NameError) -------------------
    print("\n[RUN] Llamando persist_trace ...")
    result = await svc.persist_trace(
        identity=identity,
        payload=payload,
        save_json=True,
        normalized_image=img,
        visualization_image=vis,
        generate_visualization=True,
    )

    # --- resultados --------------------------------------------------------
    print("\n[RESULTADO]")
    for key, value in result.items():
        print(f"  {key}: {value}")

    print("\n[VERIFICACION]")
    checks = [
        ("trace_normalized_image_path", "Imagen normalizada"),
        ("trace_manifest_json_path", "Manifest JSON"),
        ("trace_json_path", "JSON route-B"),
    ]
    ok = True
    for field, label in checks:
        path_val = result.get(field)
        if path_val and Path(path_val).exists():
            size = Path(path_val).stat().st_size
            print(f"  [OK]  {label}: {path_val}  ({size} bytes)")
        elif path_val:
            print(f"  [ERR] {label}: archivo NO existe en disco -> {path_val}")
            ok = False
        else:
            print(f"  [--]  {label}: no generado (campo None)")

    warnings = result.get("trace_warnings", [])
    if warnings:
        print(f"\n  [WARN] {len(warnings)} advertencia(s):")
        for w in warnings:
            print(f"    - {w}")

    print()
    if ok:
        print("[PASS] Fix verificado: persist_trace guarda archivos correctamente.")
    else:
        print("[FAIL] Algunos archivos no se generaron. Revisar warnings.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, default=None,
                        help="Ruta opcional a una imagen .jpg/.png real")
    args = parser.parse_args()
    asyncio.run(run_test(args.image))
