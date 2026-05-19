from __future__ import annotations

from pydantic import BaseModel


class ComparisonResponse(BaseModel):
    compare_profile_source: str
    compare_profile_summary: dict[str, float | int | str | bool | None]
    compare_input_stats: dict[str, float]
    compare_output_stats: dict[str, float]
    compare_output_shape: list[int]
    compare_output_image_base64: str
    compare_output_image_url: str | None = None
    comparison_visualization_base64: str
    comparison_visualization_url: str | None = None
    compare_profile_payload: dict[str, float | int | str | bool | list[int] | dict | None]


class AnalysisResponse(BaseModel):
    curve: dict[str, float | str | bool | list[dict[str, float | int]] | dict[str, float | int | str]]
    color_index: dict[str, float | str | list[dict[str, float | int | str]]]
    segmentation: dict[str, float | str | list[str] | list[dict[str, float]] | dict[str, float]]
    heatmap_data: list[list[float]]
    measurements: list[dict[str, float | str | None]]


class NormalizationResponse(BaseModel):
    success: bool = True
    profile_source: str
    implementation_map: list[str]
    closest_profile_key: str
    closest_profile_distance: float
    closest_profile_summary: dict[str, float | int | str | bool | None]
    input_stats: dict[str, float]
    output_stats: dict[str, float]
    output_shape: list[int]
    output_image_base64: str
    output_image_url: str | None = None
    runtime_metadata: dict[str, dict[str, float | int | str | bool | list[int] | None]]
    analysis: AnalysisResponse | None = None
    comparison: ComparisonResponse | None = None


class ProfileStorageStatusResponse(BaseModel):
    profiles_dir: str
    index_file: str
    source_count: int
    source_sample_keys: list[str]
    redis_key: str
    redis_count: int
    redis_sample_keys: list[str]
    mongo_collection: str
    mongo_count: int
    mongo_sample_keys: list[str]
    default_profile_source: str


class ProfileBootstrapResponse(BaseModel):
    loaded_to_redis: int
    loaded_to_mongo: int
    status: ProfileStorageStatusResponse
