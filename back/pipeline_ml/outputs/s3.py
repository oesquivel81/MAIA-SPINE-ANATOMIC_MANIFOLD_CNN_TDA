from __future__ import annotations

from typing import Any


class S3OutputWriter:
    def __init__(self, enabled: bool, bucket: str, prefix: str) -> None:
        self.enabled = enabled
        self.bucket = bucket
        self.prefix = prefix

    def write_payload(self, request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled"}

        # Placeholder para integrar boto3 con el cliente S3 del proyecto.
        return {
            "status": "queued",
            "bucket": self.bucket,
            "key": f"{self.prefix}/{request_id}/output.json",
            "size": len(str(payload)),
        }
