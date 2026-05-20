from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4
import time

from pipeline_ml.config import PipelineConfig
from pipeline_ml.context import AssetBundle, PipelineContext, PipelineResult
from pipeline_ml.logger import PipelineLogger, timed_step
from pipeline_ml.outputs import EventBridge, LocalOutputWriter, MongoMetricsWriter, S3OutputWriter
from pipeline_ml.stages import (
    IngestionStage,
    InferenceStage,
    PersistenceStage,
    PostprocessingStage,
    PreprocessingStage,
)


def parse_assets_string(full_assets: str) -> AssetBundle:
    """Formato esperado: FULL_NAME|joblib1;joblib2|res1;res2"""
    parts = (full_assets or "").split("|")
    full_name = parts[0].strip() if parts else ""

    joblib_paths: list[str] = []
    resource_paths: list[str] = []

    if len(parts) > 1 and parts[1].strip():
        joblib_paths = [p.strip() for p in parts[1].split(";") if p.strip()]

    if len(parts) > 2 and parts[2].strip():
        resource_paths = [p.strip() for p in parts[2].split(";") if p.strip()]

    return AssetBundle(full_name=full_name, joblib_paths=joblib_paths, resource_paths=resource_paths)


class PipelineML:
    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()
        self.logger = PipelineLogger(
            enabled=self.config.debug.enabled,
            verbose=self.config.debug.verbose,
        )

        self.local_writer = LocalOutputWriter()
        self.s3_writer = S3OutputWriter(
            enabled=self.config.routing.write_outputs_to_s3,
            bucket=self.config.paths.s3_bucket,
            prefix=self.config.paths.s3_prefix,
        )
        self.mongo_writer = MongoMetricsWriter(
            enabled=self.config.routing.write_metrics_to_mongo,
            database=self.config.paths.mongo_database,
            collection=self.config.paths.mongo_collection,
        )
        self.event_bridge = EventBridge(
            kafka_enabled=self.config.routing.publish_events_to_kafka,
            lambda_enabled=self.config.routing.invoke_lambda_for_metrics,
            kafka_topic=self.config.paths.kafka_topic,
            lambda_name=self.config.paths.lambda_function_name,
        )

        self.stages = [
            IngestionStage(),
            PreprocessingStage(),
            InferenceStage(),
            PostprocessingStage(),
            PersistenceStage(),
        ]

    def run(self, image: Any, full_assets: str, request_id: str | None = None) -> PipelineResult:
        req_id = request_id or str(uuid4())
        assets = parse_assets_string(full_assets)

        base_dir = Path(self.config.paths.local_artifacts_dir)
        work_dir = base_dir / req_id
        work_dir.mkdir(parents=True, exist_ok=True)

        context = PipelineContext.now(request_id=req_id, assets=assets, work_dir=work_dir)
        context.metadata["normalization_profile_jsonl"] = self.config.paths.normalization_profile_jsonl

        payload: dict[str, Any] = {"image": image, "request_id": req_id}

        self.logger.info(f"Inicio request_id={req_id}")
        self.logger.debug(
            f"Modo colab={self.config.routing.colab_mode}, instance={self.config.routing.instance_mode}"
        )

        for stage in self.stages:
            payload, elapsed_ms = timed_step(
                stage.name,
                lambda st=stage, pl=payload: st.run(pl, context, self.logger),
                self.logger,
            )
            context.step_durations_ms[stage.name] = elapsed_ms
            context.progress_messages.append(f"{stage.name}:ok:{elapsed_ms:.2f}ms")

            stage.confirm_visual(
                payload,
                debug_enabled=self.config.debug.enabled,
                save_csv=self.config.debug.save_debug_artifacts,
                debug_dir=context.debug_dir,
            )

            if self.config.routing.publish_events_to_kafka or self.config.routing.invoke_lambda_for_metrics:
                self.event_bridge.publish_progress(
                    {
                        "type": "stage_completed",
                        "request_id": req_id,
                        "stage": stage.name,
                        "elapsed_ms": elapsed_ms,
                    }
                )

        total_ms = (time.time() - context.started_at) * 1000.0
        metrics = {
            "request_id": req_id,
            "total_ms": total_ms,
            "step_durations_ms": context.step_durations_ms,
            "progress_messages": context.progress_messages,
        }

        outputs = {
            "request_id": req_id,
            "full_name": assets.full_name,
            "joblib_paths": assets.joblib_paths,
            "resource_paths": assets.resource_paths,
            "payload": payload,
        }

        if self.config.routing.write_local_artifacts:
            self.local_writer.write_json(context.outputs_dir / "output.json", outputs)
            self.local_writer.write_json(context.metrics_dir / "metrics.json", metrics)

        s3_result = self.s3_writer.write_payload(req_id, outputs)
        mongo_result = self.mongo_writer.write_metrics(metrics)

        outputs["s3"] = s3_result
        outputs["mongo"] = mongo_result

        if self.config.debug.print_step_summary:
            self.logger.info(f"Pipeline completado en {total_ms:.2f} ms")
            self.logger.info(f"Resumen de etapas: {context.step_durations_ms}")

        return PipelineResult(
            request_id=req_id,
            ok=True,
            message="pipeline_ml finalizado",
            outputs=outputs,
            metrics=metrics,
        )


def run_pipeline_entry(
    image: Any,
    full_assets: str,
    config_file: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Metodo de entrada unico para Colab o instancia.

    Args:
        image: imagen de entrada del pipeline.
        full_assets: string concatenado con formato FULL_NAME|joblib1;joblib2|res1;res2.
        config_file: archivo JSON con flags y rutas.
        request_id: id opcional para trazar ejecucion.
    """
    config = PipelineConfig.from_json_file(config_file)
    pipeline = PipelineML(config=config)
    result = pipeline.run(image=image, full_assets=full_assets, request_id=request_id)
    return asdict(result)


def run_pipeline_main(
    pipeline_input: dict[str, Any],
    config_file: str | None = None,
) -> dict[str, Any]:
    """Metodo principal para Colab con una sola entrada.

    Entrada esperada en `pipeline_input`:
    - image: imagen de entrada
    - full_assets: string FULL_NAME|joblib1;joblib2|res1;res2
    - request_id (opcional)
    """
    if "image" not in pipeline_input:
        raise ValueError("pipeline_input requiere la llave 'image'")
    if "full_assets" not in pipeline_input:
        raise ValueError("pipeline_input requiere la llave 'full_assets'")

    config = PipelineConfig.from_json_file(config_file)
    pipeline = PipelineML(config=config)
    result = pipeline.run(
        image=pipeline_input["image"],
        full_assets=str(pipeline_input["full_assets"]),
        request_id=pipeline_input.get("request_id"),
    )
    return asdict(result)
