from botocore.exceptions import ClientError
import boto3

from app.core.config import Settings


class S3Component:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            endpoint_url=settings.aws_s3_endpoint_url,
        )

    @property
    def client(self):
        return self._client

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._settings.aws_s3_bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._settings.aws_s3_bucket)
