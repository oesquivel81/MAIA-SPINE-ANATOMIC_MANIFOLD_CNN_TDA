from pydantic import BaseModel


class FileMetadataResponse(BaseModel):
    id: str
    file_name: str
    content_type: str | None
    size_bytes: int
    s3_bucket: str
    s3_key: str
    created_at: str
