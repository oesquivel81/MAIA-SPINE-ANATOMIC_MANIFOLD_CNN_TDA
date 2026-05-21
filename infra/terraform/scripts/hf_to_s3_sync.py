from __future__ import annotations

import os
import sys
from pathlib import Path


def _split_patterns(value: str) -> list[str] | None:
    parts = [item.strip() for item in value.split(",") if item.strip()]
    return parts or None


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _upload_dir_to_s3(local_dir: Path, bucket: str, prefix: str, region: str) -> int:
    import boto3

    s3 = boto3.client("s3", region_name=region or None)
    uploaded = 0

    for path in local_dir.rglob("*"):
        if not path.is_file():
            continue

        rel = path.relative_to(local_dir).as_posix()
        if prefix:
            key = f"{prefix.rstrip('/')}/{rel}"
        else:
            key = rel

        s3.upload_file(str(path), bucket, key)
        uploaded += 1

    return uploaded


def main() -> int:
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        print(
            "[ERROR] huggingface_hub is required. Install with: pip install huggingface_hub boto3",
            file=sys.stderr,
        )
        print(f"[DETAIL] {exc}", file=sys.stderr)
        return 2

    try:
        token = os.environ.get("HF_TOKEN", "").strip()
        repo_id = _require_env("HF_REPO_ID")
        repo_type = os.environ.get("HF_REPO_TYPE", "dataset").strip() or "dataset"
        revision = os.environ.get("HF_REVISION", "").strip() or None
        allow_patterns = _split_patterns(os.environ.get("HF_ALLOW_PATTERNS", ""))
        ignore_patterns = _split_patterns(os.environ.get("HF_IGNORE_PATTERNS", ""))
        local_dir = Path(os.environ.get("HF_LOCAL_DIR", "./.hf_cache")).resolve()
        bucket = _require_env("HF_TARGET_S3_BUCKET")
        prefix = os.environ.get("HF_TARGET_S3_PREFIX", "huggingface-sync").strip()
        region = os.environ.get("AWS_REGION", "").strip()

        local_dir.mkdir(parents=True, exist_ok=True)

        print(f"[INFO] Downloading from Hugging Face repo: {repo_type}/{repo_id}")
        snapshot_path = snapshot_download(
            repo_id=repo_id,
            repo_type=repo_type,
            token=token or None,
            revision=revision,
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )

        print(f"[INFO] Snapshot downloaded to: {snapshot_path}")
        uploaded = _upload_dir_to_s3(local_dir=local_dir, bucket=bucket, prefix=prefix, region=region)
        print(f"[INFO] Uploaded {uploaded} files to s3://{bucket}/{prefix}")
        return 0
    except Exception as exc:
        print(f"[ERROR] Failed to sync Hugging Face to S3: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
