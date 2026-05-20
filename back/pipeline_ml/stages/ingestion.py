from __future__ import annotations

from typing import Any

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.stages.base import PipelineStage
from pipeline_ml.utils.stage_report import StageReport


class IngestionStage(PipelineStage):
    name = "ingestion"

    def run(self, payload: dict[str, Any], context: PipelineContext, logger: PipelineLogger) -> dict[str, Any]:
        image = payload.get("image")
        if image is None:
            raise ValueError("El pipeline requiere una imagen de entrada")

        logger.info("Ingestion: imagen recibida correctamente")
        payload["ingested"] = True
        return payload

    def describe_output(self, payload: dict[str, Any]) -> StageReport:
        """Campos esperados: image, request_id, ingested."""
        report = StageReport(stage_name=self.name)
        for key in ("image", "request_id", "ingested"):
            report.add(key, payload.get(key, "<ausente>"))
        return report
