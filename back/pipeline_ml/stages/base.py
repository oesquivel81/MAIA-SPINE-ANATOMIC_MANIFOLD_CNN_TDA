from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.utils.stage_report import StageReport, build_report


class PipelineStage(ABC):
    name = "base"

    @abstractmethod
    def run(self, payload: dict[str, Any], context: PipelineContext, logger: PipelineLogger) -> dict[str, Any]:
        raise NotImplementedError

    def describe_output(self, payload: dict[str, Any]) -> StageReport:
        """Construye un StageReport con las columnas/estructura del payload.

        Cada etapa concreta puede sobreescribir este metodo para exponer
        solo los campos relevantes o agregar columnas especificas.
        """
        return build_report(self.name, payload)

    def confirm_visual(
        self,
        payload: dict[str, Any],
        debug_enabled: bool = True,
        save_csv: bool = False,
        debug_dir: Path | None = None,
    ) -> StageReport:
        """Confirmacion visual e impresion de estructura por etapa.

        Llama automaticamente al finalizar cada etapa desde el entrypoint.
        """
        report = self.describe_output(payload)
        if debug_enabled:
            report.print_visual()
        if save_csv and debug_dir is not None:
            csv_path = report.write_csv(debug_dir)
            if debug_enabled:
                print(f"  [DEBUG] CSV de estructura guardado: {csv_path}\n")
        return report
