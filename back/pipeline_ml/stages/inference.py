from __future__ import annotations

from typing import Any
from pathlib import Path

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.models import ClusteringModel, CnnCurveModel, StudentManifoldCnnModel
from pipeline_ml.stages.base import PipelineStage
from pipeline_ml.utils.stage_report import StageReport


class InferenceStage(PipelineStage):
    name = "inference"

    def __init__(self) -> None:
        self.cnn_curve = CnnCurveModel()
        self.student_manifold_cnn = StudentManifoldCnnModel()
        self.clustering = ClusteringModel()

    def run(self, payload: dict[str, Any], context: PipelineContext, logger: PipelineLogger) -> dict[str, Any]:
        missing = []
        for path in context.assets.joblib_paths:
            if not Path(path).exists():
                missing.append(path)

        if missing:
            logger.warn("Inference: se detectaron joblibs ausentes")
            payload["missing_joblibs"] = missing
        else:
            logger.info("Inference: joblibs detectados correctamente")

        logger.info("Inference: ejecutando modelo cnn_curve")
        curve_output = self.cnn_curve.predict(payload.get("image"))

        logger.info("Inference: ejecutando modelo student_manifold_cnn")
        manifold_output = self.student_manifold_cnn.predict(payload.get("image"), curve_output)

        logger.info("Inference: ejecutando modelo clustering")
        clustering_output = self.clustering.predict(manifold_output)

        payload["predictions"] = {
            "status": "ok",
            "full_name": context.assets.full_name,
            "models": {
                "cnn_curve": curve_output,
                "student_manifold_cnn": manifold_output,
                "clustering": clustering_output,
            },
        }
        return payload

    def describe_output(self, payload: dict[str, Any]) -> StageReport:
        """Campos esperados: predictions con submodelos cnn_curve, student_manifold_cnn, clustering."""
        report = StageReport(stage_name=self.name)
        report.add("missing_joblibs", payload.get("missing_joblibs", []))
        predictions = payload.get("predictions", {})
        report.add("predictions.status", predictions.get("status", "<ausente>"))
        report.add("predictions.full_name", predictions.get("full_name", "<ausente>"))
        models = predictions.get("models", {})
        for model_name in ("cnn_curve", "student_manifold_cnn", "clustering"):
            m = models.get(model_name, {})
            report.add(f"models.{model_name}.status", m.get("status", "<ausente>"))
            for k, v in m.items():
                if k != "status":
                    report.add(f"models.{model_name}.{k}", v)
        return report
