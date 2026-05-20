from __future__ import annotations

from typing import Any

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.stages.base import PipelineStage
from pipeline_ml.utils.stage_report import StageReport


class PostprocessingStage(PipelineStage):
    name = "postprocessing"

    def run(self, payload: dict[str, Any], context: PipelineContext, logger: PipelineLogger) -> dict[str, Any]:
        logger.info("Postprocessing: empaquetado base completado")
        payload["postprocessed"] = True
        return payload

    def describe_output(self, payload: dict[str, Any]) -> StageReport:
        """Campos esperados: predictions, postprocessed."""
        report = StageReport(stage_name=self.name)
        predictions = payload.get("predictions", {})
        report.add("predictions.status", predictions.get("status", "<ausente>"))
        report.add("predictions.full_name", predictions.get("full_name", "<ausente>"))
        report.add(
            "predictions.clustering.cluster_id",
            predictions.get("models", {}).get("clustering", {}).get("cluster_id", "<ausente>"),
        )
        report.add("postprocessed", payload.get("postprocessed", "<ausente>"))
        return report
