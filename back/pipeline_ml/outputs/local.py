from __future__ import annotations

from pathlib import Path
import json
from typing import Any


class LocalOutputWriter:
    def write_json(self, target_file: Path, payload: dict[str, Any]) -> Path:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return target_file
