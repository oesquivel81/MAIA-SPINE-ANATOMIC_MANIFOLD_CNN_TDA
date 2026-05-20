from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI Spring Style"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    aws_region: str = "us-east-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    aws_s3_bucket: str = "project-files"
    aws_s3_endpoint_url: str | None = "http://localhost:4566"  # LocalStack default endpoint

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "app_db"
    mongo_collection: str = "file_metadata"
    mongo_profiles_collection: str = "normalization_profiles"

    redis_uri: str = "redis://localhost:6379/0"
    normalization_profile_source: str = "redis"
    normalization_bootstrap_on_startup: bool = True
    normalization_debug_enabled: bool = False
    normalization_debug_save_json: bool = True
    normalization_traceability_enabled: bool = True
    normalization_traceability_output_dir: str = "normalization_traceability"
    normalization_trace_visualization_enabled: bool = True
    normalization_trace_redis_enabled: bool = False
    normalization_trace_mongo_enabled: bool = False
    normalization_trace_route_b_enabled: bool = True
    normalization_trace_route_b_format: str = "auto"
    normalization_trace_s3_enabled: bool = False
    normalization_trace_s3_prefix: str = "normalization-traceability"
    redis_normalization_trace_prefix: str = "normalization_trace"
    mongo_normalization_traces_collection: str = "normalization_traces"

    model_config = SettingsConfigDict(
        env_file=("application.properties", ".env"),
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
