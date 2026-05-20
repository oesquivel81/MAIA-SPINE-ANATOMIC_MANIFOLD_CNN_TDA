from __future__ import annotations

from typing import Any

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.stages.base import PipelineStage
from pipeline_ml.utils.stage_report import StageReport


class PersistenceStage(PipelineStage):
    name = "persistence"

    def run(self, payload: dict[str, Any], context: PipelineContext, logger: PipelineLogger) -> dict[str, Any]:
        logger.info("Persistence: etapa lista para redirecciones de salida")
        payload["persistence_ready"] = True
        return payload

    def describe_output(self, payload: dict[str, Any]) -> StageReport:
        """Campos esperados: request_id, postprocessed, persistence_ready."""
        report = StageReport(stage_name=self.name)
        for key in ("request_id", "postprocessed", "persistence_ready"):
            report.add(key, payload.get(key, "<ausente>"))
        return report
