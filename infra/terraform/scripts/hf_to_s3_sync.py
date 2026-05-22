from __future__ import annotations

import fnmatch
import io
import os
import sys


def _split_patterns(value: str) -> list[str] | None:
    parts = [item.strip() for item in value.split(",") if item.strip()]
    return parts or None


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _matches(path: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def _stream_file_to_s3(url: str, headers: dict, s3_client, bucket: str, key: str) -> None:
    """Stream a file from a URL directly into S3 without writing to disk."""
    import requests

    with requests.get(url, headers=headers, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        content_length = resp.headers.get("Content-Length")
        fileobj = io.BytesIO()
        for chunk in resp.iter_content(chunk_size=8 * 1024 * 1024):  # 8 MB chunks
            if chunk:
                fileobj.write(chunk)
        fileobj.seek(0)
        extra = {"ContentLength": int(content_length)} if content_length else {}
        s3_client.upload_fileobj(fileobj, bucket, key, ExtraArgs=extra if extra else None)


def main() -> int:
    try:
        import boto3
        import requests
        from huggingface_hub import HfApi, hf_hub_url
    except Exception as exc:
        print(
            "[ERROR] Required packages missing. Install with: pip install huggingface_hub boto3 requests",
            file=sys.stderr,
        )
        print(f"[DETAIL] {exc}", file=sys.stderr)
        return 2

    try:
        token = os.environ.get("HF_TOKEN", "").strip()
        repo_id = _require_env("HF_REPO_ID")
        repo_type = os.environ.get("HF_REPO_TYPE", "dataset").strip() or "dataset"
        revision = os.environ.get("HF_REVISION", "").strip() or "main"
        allow_patterns = _split_patterns(os.environ.get("HF_ALLOW_PATTERNS", ""))
        ignore_patterns = _split_patterns(os.environ.get("HF_IGNORE_PATTERNS", ""))
        bucket = _require_env("HF_TARGET_S3_BUCKET")
        prefix = os.environ.get("HF_TARGET_S3_PREFIX", "huggingface-sync").strip()
        region = os.environ.get("AWS_REGION", "").strip()

        auth_headers = {"Authorization": f"Bearer {token}"} if token else {}

        api = HfApi(token=token or None)
        s3 = boto3.client("s3", region_name=region or None)

        print(f"[INFO] Listing files in {repo_type}/{repo_id}@{revision} ...")
        repo_files = api.list_repo_files(
            repo_id=repo_id,
            repo_type=repo_type,
            revision=revision,
        )

        uploaded = 0
        skipped = 0
        for file_path in repo_files:
            if not _matches(file_path, allow_patterns):
                skipped += 1
                continue
            if ignore_patterns and _matches(file_path, ignore_patterns):
                skipped += 1
                continue

            url = hf_hub_url(
                repo_id=repo_id,
                filename=file_path,
                repo_type=repo_type,
                revision=revision,
            )
            s3_key = f"{prefix.rstrip('/')}/{file_path}" if prefix else file_path

            print(f"[INFO] Streaming  {file_path}  →  s3://{bucket}/{s3_key}")
            _stream_file_to_s3(url, auth_headers, s3, bucket, s3_key)
            uploaded += 1

        print(f"[INFO] Done. {uploaded} file(s) uploaded, {skipped} skipped.")
        return 0

    except Exception as exc:
        print(f"[ERROR] Failed to sync Hugging Face to S3: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
