from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import time


@dataclass
class AssetBundle:
    full_name: str
    joblib_paths: list[str] = field(default_factory=list)
    resource_paths: list[str] = field(default_factory=list)


@dataclass
class PipelineContext:
    request_id: str
    started_at: float
    assets: AssetBundle
    work_dir: Path
    outputs_dir: Path
    metrics_dir: Path
    temp_dir: Path
    debug_dir: Path = field(default_factory=lambda: Path("./debug"))

    progress_messages: list[str] = field(default_factory=list)
    step_durations_ms: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def now(cls, request_id: str, assets: AssetBundle, work_dir: Path) -> "PipelineContext":
        outputs_dir = work_dir / "outputs"
        metrics_dir = work_dir / "metrics"
        temp_dir = work_dir / "tmp"
        debug_dir = work_dir / "debug"

        outputs_dir.mkdir(parents=True, exist_ok=True)
        metrics_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        debug_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            request_id=request_id,
            started_at=time.time(),
            assets=assets,
            work_dir=work_dir,
            outputs_dir=outputs_dir,
            metrics_dir=metrics_dir,
            temp_dir=temp_dir,
            debug_dir=debug_dir,
        )


@dataclass
class PipelineResult:
    request_id: str
    ok: bool
    message: str
    outputs: dict[str, Any]
    metrics: dict[str, Any]
