from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizationPipelineContext:
    closest_profile: dict[str, Any]
    closest_profile_distance: float
    applied_steps: list[str] = field(default_factory=list)
    runtime_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
