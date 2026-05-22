#!/usr/bin/env python3
"""Script de prueba end-to-end: genera imagen de ruido y corre Pipeline B.

Uso desde dentro del pod o desde el directorio back/:
    python scripts/test_pipeline_noise.py

Variables de entorno opcionales:
    MONGO_URI       mongodb://localhost:27017   (default)
    KAFKA_SERVERS   ""                          (vacío = Kafka deshabilitado)
    REQUEST_ID      uuid generado automáticamente si no se pasa

Qué valida:
    1. Pipeline B completa las 9 etapas sin error
    2. Métricas de cada stage se guardan en Mongo (si MONGO_URI apunta a instancia activa)
    3. Kafka publica eventos por stage (si KAFKA_SERVERS está configurado)
    4. El flush final reporta ok/partial
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Asegura que se importa desde back/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from pipeline_ml.config import DebugFlags, PipelineConfig, PipelinePaths, RoutingFlags
from pipeline_ml.entrypoint import PipelineML

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
KAFKA_SERVERS = os.getenv("KAFKA_SERVERS", "")
REQUEST_ID = os.getenv("REQUEST_ID", None)

ENABLE_MONGO = bool(MONGO_URI.strip())
ENABLE_KAFKA = bool(KAFKA_SERVERS.strip())


def generate_noise_image(height: int = 512, width: int = 256) -> np.ndarray:
    """Genera imagen grayscale de ruido gaussiano similar a una radiografía espinal."""
    rng = np.random.default_rng(42)
    # Ruido base
    noise = rng.normal(loc=128, scale=40, size=(height, width)).astype(np.uint8)
    # Gradiente vertical para simular columna
    gradient = np.linspace(60, 200, height, dtype=np.float32).reshape(-1, 1)
    gradient = np.broadcast_to(gradient, (height, width)).copy()
    blended = (0.4 * noise + 0.6 * gradient).clip(0, 255).astype(np.uint8)
    return blended


def main() -> None:
    print("=" * 60)
    print("TEST PIPELINE B — imagen de ruido")
    print(f"  MONGO_URI     : {MONGO_URI if ENABLE_MONGO else '(deshabilitado)'}")
    print(f"  KAFKA_SERVERS : {KAFKA_SERVERS if ENABLE_KAFKA else '(deshabilitado)'}")
    print("=" * 60)

    image = generate_noise_image()
    print(f"Imagen generada: shape={image.shape} dtype={image.dtype}")

    config = PipelineConfig(
        debug=DebugFlags(
            enabled=True,
            verbose=False,
            print_step_summary=True,
            save_debug_artifacts=False,
            plots_show=False,
        ),
        routing=RoutingFlags(
            colab_mode=False,
            instance_mode=True,          # Camino B
            write_local_artifacts=True,
            write_outputs_to_s3=False,
            write_metrics_to_mongo=ENABLE_MONGO,
            publish_events_to_kafka=ENABLE_KAFKA,
            invoke_lambda_for_metrics=False,
        ),
        paths=PipelinePaths(
            mongo_uri=MONGO_URI,
            mongo_database="maia",
            mongo_collection="pipeline_stage_metrics",
            kafka_bootstrap_servers=KAFKA_SERVERS,
            kafka_topic_prefix="pipeline-stage",
        ),
    )

    pipeline = PipelineML(config=config)

    t0 = time.time()
    result = pipeline.run(
        image=image,
        full_assets="test_patient_noise||",
        request_id=REQUEST_ID,
    )
    elapsed = (time.time() - t0) * 1000.0

    print("\n--- RESULTADO ---")
    print(f"request_id : {result.request_id}")
    print(f"ok         : {result.ok}")
    print(f"total_ms   : {elapsed:.2f} ms")

    print("\n--- DURACIONES POR STAGE ---")
    for stage, ms in result.metrics.get("step_durations_ms", {}).items():
        print(f"  {stage:<30} {ms:>10.2f} ms")

    stage_sinks = result.metrics.get("stage_sinks")
    if stage_sinks:
        print("\n--- FLUSH STAGE SINKS (Camino B) ---")
        print(json.dumps(stage_sinks, indent=2, default=str))
    else:
        print("\n[stage_sinks no presente — instance_mode no activo o sin sinks configurados]")

    if not result.ok:
        print(f"\nERROR: {result.message}")
        sys.exit(1)

    print("\nTest completado con éxito.")


if __name__ == "__main__":
    main()
