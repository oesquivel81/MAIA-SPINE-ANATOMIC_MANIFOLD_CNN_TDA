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
    nombre: Annotated[str, Form(description="Nombre del paciente")] = "paciente",
    sexo: Annotated[str, Form(description="Sexo (M/F)")] = "",
    edad: Annotated[str, Form(description="Edad en años")] = "",
    peso: Annotated[str, Form(description="Peso en kg")] = "",
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

    # Construir patient_key desde datos del paciente
    parts = [nombre.strip().upper().replace(" ", "_") or "PACIENTE"]
    if sexo.strip():
        parts.append(sexo.strip().upper())
    if edad.strip():
        parts.append(f"{edad.strip()}A")
    if peso.strip():
        parts.append(f"{peso.strip()}KG")
    patient_key = "_".join(parts)

    # Resolver modelos desde S3 (o retornar path local si ya existe en caché)
    j0 = _resolve_model_path(settings.pipeline_binary_curve_model_path, settings.aws_s3_bucket, settings.aws_region, settings.pipeline_models_local_dir)
    j1 = _resolve_model_path(settings.pipeline_student_patch_model_path, settings.aws_s3_bucket, settings.aws_region, settings.pipeline_models_local_dir)
    j2 = _resolve_model_path(settings.pipeline_clustering_model_path, settings.aws_s3_bucket, settings.aws_region, settings.pipeline_models_local_dir)
    resolved_assets = f"{patient_key}|{j0};{j1};{j2}|"

    pipeline = _build_pipeline(settings)
    result = pipeline.run(image=image, full_assets=resolved_assets)

    clinical = result.outputs.get("clinical_result")
    if not clinical:
        raise HTTPException(status_code=500, detail="El pipeline no generó clinical_result")

    # Subir imágenes a S3 y reemplazar rutas con presigned URLs
    _upload_artifacts_and_sign(clinical, settings.aws_s3_bucket, settings.aws_region)

    return clinical


def _upload_artifacts_and_sign(clinical: dict, bucket: str, region: str, expires_in: int = 3600) -> None:
    """Sube archivos locales del pipeline a S3 y reemplaza las rutas con presigned URLs."""
    s3 = boto3.client("s3", region_name=region)
    container_root = Path("/app")
    artifacts_root = (container_root / "pipeline_ml_artifacts").resolve()

    def _upload_and_sign(local_path: str | None) -> str | None:
        if not local_path:
            return local_path
        p = Path(local_path)
        abs_p = p if p.is_absolute() else container_root / p
        # Seguridad: solo permitir rutas dentro de pipeline_ml_artifacts
        try:
            abs_p.resolve().relative_to(artifacts_root)
        except ValueError:
            return local_path
        if not abs_p.exists():
            return local_path
        try:
            s3_key = str(abs_p.relative_to(container_root)).replace("\\", "/")
        except ValueError:
            s3_key = str(p).replace("\\", "/").lstrip("/")
        try:
            if s3_key.endswith(".png") or s3_key.endswith(".jpg") or s3_key.endswith(".jpeg"):
                content_type = "image/png"
            elif s3_key.endswith(".csv"):
                content_type = "text/csv"
            elif s3_key.endswith(".json"):
                content_type = "application/json"
            else:
                content_type = "application/octet-stream"
            s3.upload_file(str(abs_p), bucket, s3_key, ExtraArgs={"ContentType": content_type})
            return s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": s3_key},
                ExpiresIn=expires_in,
            )
        except Exception:
            return local_path  # Si falla, retornar ruta original sin romper la respuesta

    # ── Imágenes (excluye binary_mask, curve_mask, combined_signal, spatial_index_panel) ──
    images = clinical.get("images", {})
    for field in ("analysis_grid", "gap_peak_analysis", "normalized_image"):
        images[field] = _upload_and_sign(images.get(field))
    # Eliminar campos excluidos de la respuesta
    for field in ("binary_mask", "curve_mask", "combined_signal", "spatial_index_panel"):
        images.pop(field, None)

    images["patch_inputs"] = [_upload_and_sign(p) for p in images.get("patch_inputs", [])]

    # ── CSV y JSON de predictions ──────────────────────────────────────
    predictions = clinical.get("predictions", {})
    for field in ("summary_csv_path", "regions_csv_path", "clinical_json_path", "clinical_figure_path"):
        predictions[field] = _upload_and_sign(predictions.get(field))

    # ── CSV de gap_summary ─────────────────────────────────────────────
    gap_summary = clinical.get("gap_summary", {})
    gap_summary["vertebra_csv_path"] = _upload_and_sign(gap_summary.get("vertebra_csv_path"))
