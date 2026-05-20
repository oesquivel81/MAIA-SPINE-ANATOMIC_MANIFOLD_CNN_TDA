from __future__ import annotations

from typing import Any

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.stages.base import PipelineStage
from pipeline_ml.utils.stage_report import StageReport


class PreprocessingStage(PipelineStage):
    name = "preprocessing"

    def run(self, payload: dict[str, Any], context: PipelineContext, logger: PipelineLogger) -> dict[str, Any]:
        logger.info("Preprocessing: paso base ejecutado")
        payload["preprocessed"] = True
        return payload

    def describe_output(self, payload: dict[str, Any]) -> StageReport:
        """Campos esperados: image, ingested, preprocessed."""
        report = StageReport(stage_name=self.name)
        for key in ("image", "ingested", "preprocessed"):
            report.add(key, payload.get(key, "<ausente>"))
        return report
