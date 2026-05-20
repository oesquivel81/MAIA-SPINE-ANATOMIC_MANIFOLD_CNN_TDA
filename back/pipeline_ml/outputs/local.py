from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


class _SafeEncoder(json.JSONEncoder):
    """Encoder que convierte tipos no serializables a representaciones seguras."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.ndarray):
            return {"__ndarray__": True, "shape": list(obj.shape), "dtype": str(obj.dtype)}
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        return super().default(obj)


class LocalOutputWriter:
    def write_json(self, target_file: Path, payload: dict[str, Any]) -> Path:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, cls=_SafeEncoder),
            encoding="utf-8",
        )
        return target_file
