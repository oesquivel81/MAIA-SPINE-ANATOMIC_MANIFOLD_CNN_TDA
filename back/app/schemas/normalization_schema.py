from __future__ import annotations

from pydantic import BaseModel


class ComparisonResponse(BaseModel):
    compare_profile_source: str
    compare_profile_summary: dict[str, float | int | str | bool | None]
    compare_input_stats: dict[str, float]
    compare_output_stats: dict[str, float]
    compare_output_shape: list[int]
    compare_output_image_base64: str
    comparison_visualization_base64: str
    compare_profile_payload: dict[str, float | int | str | bool | list[int] | dict | None]


class NormalizationResponse(BaseModel):
    profile_source: str
    implementation_map: list[str]
    closest_profile_key: str
    closest_profile_distance: float
    closest_profile_summary: dict[str, float | int | str | bool | None]
    input_stats: dict[str, float]
    output_stats: dict[str, float]
    output_shape: list[int]
    output_image_base64: str
    runtime_metadata: dict[str, dict[str, float | int | str | bool | list[int] | None]]
    comparison: ComparisonResponse | None = None
