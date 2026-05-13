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
    aws_s3_endpoint_url: str | None = None

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "app_db"
    mongo_collection: str = "file_metadata"

    redis_uri: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
