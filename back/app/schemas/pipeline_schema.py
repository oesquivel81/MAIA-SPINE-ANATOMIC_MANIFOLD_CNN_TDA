from __future__ import annotations

from pydantic import BaseModel


class PipelineImagesDTO(BaseModel):
    analysis_grid: str | None = None
    gap_peak_analysis: str | None = None
    normalized_image: str | None = None
    patch_inputs: list[str] = []


class PipelinePredictionsDTO(BaseModel):
    inference_done: bool = False
    cobb_angle_deg: float | None = None
    cobb_severity: str | None = None
    dominant_cluster_id: int | None = None
    n_clusters_detected: int | None = None
    clinical_json_path: str | None = None
    clinical_figure_path: str | None = None
    summary_csv_path: str | None = None
    regions_csv_path: str | None = None


class PipelineGapSummaryDTO(BaseModel):
    mean_gap_spacing: float | None = None
    std_gap_spacing: float | None = None
    n_peaks: int | None = None
    n_gap_peaks: int | None = None
    vertebra_csv_path: str | None = None


class PipelineNerveCurveDTO(BaseModel):
    """CSV de la curva espinal (nervio) con coordenadas y arclength."""
    curve_csv_path: str | None = None


class PipelineClinicalResultDTO(BaseModel):
    """DTO de salida del endpoint de análisis de columna.

    Refleja exactamente el dict generado por ``_build_clinical_result``
    en ``entrypoint.py``.
    """

    request_id: str
    patient_name: str
    images: PipelineImagesDTO
    predictions: PipelinePredictionsDTO
    gap_summary: PipelineGapSummaryDTO
    nerve_curve: PipelineNerveCurveDTO = PipelineNerveCurveDTO()

    @classmethod
    def from_pipeline_output(cls, outputs: dict) -> "PipelineClinicalResultDTO":
        """Construye el DTO desde el dict devuelto por ``run_pipeline_main``."""
        cr = outputs.get("clinical_result") or {}
        return cls(
            request_id=cr.get("request_id", outputs.get("request_id", "")),
            patient_name=cr.get("patient_name", outputs.get("full_name", "")),
            images=PipelineImagesDTO(**(cr.get("images") or {})),
            predictions=PipelinePredictionsDTO(**(cr.get("predictions") or {})),
            gap_summary=PipelineGapSummaryDTO(**(cr.get("gap_summary") or {})),
            nerve_curve=PipelineNerveCurveDTO(**(cr.get("nerve_curve") or {})),
        )
