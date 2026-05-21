"""Pipeline endpoint — Camino B (instance_mode).

POST /pipeline/run
  - Recibe imagen DICOM/PNG/cualquier formato soportado + assets string
  - Corre PipelineML configurado con instance_mode=True
  - Persiste métricas por stage en Mongo (fire-and-forget)
  - Publica evento por stage en Kafka (fire-and-forget)
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
import numpy as np

from pathlib import Path

import boto3

from app.core.config import Settings, get_settings
from pipeline_ml.config import DebugFlags, PipelineConfig, PipelinePaths, RoutingFlags
from pipeline_ml.entrypoint import PipelineML

router = APIRouter()


def _resolve_model_path(path: str, bucket: str, region: str, cache_dir: str) -> str:
    """Si path es una S3 key (sin '/'), descarga al cache y retorna la ruta local.
    Si path empieza con '/' se asume local (Colab). Si está vacío retorna ''."""
    if not path:
        return ""
    if path.startswith("/"):
        return path  # path local absoluto — modo Colab, no tocar
    local = Path(cache_dir) / Path(path).name
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        s3 = boto3.client("s3", region_name=region)
        s3.download_file(bucket, path, str(local))
    return str(local)


def _build_pipeline(settings: Settings) -> PipelineML:
    config = PipelineConfig(
        debug=DebugFlags(
            enabled=True,
            verbose=False,
            print_step_summary=True,
            save_debug_artifacts=False,
        ),
        routing=RoutingFlags(
            colab_mode=False,
            instance_mode=settings.pipeline_instance_mode,
            write_local_artifacts=True,
            write_outputs_to_s3=False,
            write_metrics_to_mongo=settings.pipeline_write_metrics_to_mongo,
            publish_events_to_kafka=settings.pipeline_publish_events_to_kafka,
            invoke_lambda_for_metrics=False,
        ),
        paths=PipelinePaths(
            mongo_uri=settings.mongo_uri,
            mongo_database=settings.mongo_db,
            mongo_collection=settings.pipeline_mongo_collection,
            kafka_bootstrap_servers=settings.kafka_bootstrap_servers,
            kafka_topic_prefix=settings.kafka_topic_prefix,
            binary_curve_model_path=_resolve_model_path(
                settings.pipeline_binary_curve_model_path,
                settings.aws_s3_bucket,
                settings.aws_region,
                settings.pipeline_models_local_dir,
            ),
            student_patch_model_path=_resolve_model_path(
                settings.pipeline_student_patch_model_path,
                settings.aws_s3_bucket,
                settings.aws_region,
                settings.pipeline_models_local_dir,
            ),
        ),
    )
    return PipelineML(config=config)


@router.post("/run")
async def run_pipeline(
    file: Annotated[UploadFile, File(description="Imagen de entrada (PNG/DICOM/NPY)")],
    full_assets: Annotated[str, Form(description="Assets string: FULL_NAME|joblib1;joblib2|res1;res2")] = "||",
    settings: Settings = Depends(get_settings),
) -> dict:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    # Decodificar bytes a array numpy (soporta PNG/JPG via OpenCV, NPY directo)
    try:
        import cv2

        arr = np.frombuffer(raw, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if image is None:
            # Intentar como .npy
            import io
            image = np.load(io.BytesIO(raw), allow_pickle=False)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"No se pudo decodificar imagen: {exc}") from exc

    pipeline = _build_pipeline(settings)
    result = pipeline.run(image=image, full_assets=full_assets)

    return {
        "request_id": result.request_id,
        "ok": result.ok,
        "total_ms": result.metrics.get("total_ms"),
        "step_durations_ms": result.metrics.get("step_durations_ms", {}),
        "stage_sinks": result.metrics.get("stage_sinks"),
        "progress": result.metrics.get("progress_messages", []),
    }
