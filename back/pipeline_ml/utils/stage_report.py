from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FieldDescriptor:
    """Descripcion estructural de un campo del payload."""
    key: str
    python_type: str
    shape_or_len: str
    preview: str
    stage: str = ""


@dataclass
class StageReport:
    stage_name: str
    fields: list[FieldDescriptor] = field(default_factory=list)

    def add(self, key: str, value: Any) -> None:
        self.fields.append(_describe_field(key, value, self.stage_name))

    def print_visual(self) -> None:
        """Imprime tabla de confirmacion visual en Colab / terminal."""
        border = "=" * 64
        print(f"\n{border}")
        print(f"  REPORTE ETAPA: {self.stage_name.upper()}")
        print(border)
        header = f"  {'CAMPO':<28} {'TIPO':<18} {'FORMA/LEN':<12} {'PREVIEW'}"
        print(header)
        print("-" * 64)
        for fd in self.fields:
            print(f"  {fd.key:<28} {fd.python_type:<18} {fd.shape_or_len:<12} {fd.preview}")
        print(border + "\n")

    def write_csv(self, debug_dir: Path) -> Path:
        """Escribe un CSV con la estructura del payload para deteccion de errores."""
        debug_dir.mkdir(parents=True, exist_ok=True)
        csv_path = debug_dir / f"{self.stage_name}_structure.csv"

        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["stage", "key", "python_type", "shape_or_len", "preview"],
            )
            writer.writeheader()
            for fd in self.fields:
                writer.writerow(
                    {
                        "stage": fd.stage,
                        "key": fd.key,
                        "python_type": fd.python_type,
                        "shape_or_len": fd.shape_or_len,
                        "preview": fd.preview,
                    }
                )
        return csv_path


def build_report(stage_name: str, payload: dict[str, Any]) -> StageReport:
    """Construye un StageReport a partir de las llaves del payload."""
    report = StageReport(stage_name=stage_name)
    for key, value in payload.items():
        report.add(key, value)
    return report


def _describe_field(key: str, value: Any, stage: str) -> FieldDescriptor:
    python_type = type(value).__name__

    shape_or_len = "-"
    preview = "-"

    if value is None:
        preview = "None"
    elif isinstance(value, (int, float, bool, str)):
        preview = str(value)[:60]
        shape_or_len = str(len(str(value))) if isinstance(value, str) else "scalar"
    elif isinstance(value, (list, tuple)):
        shape_or_len = str(len(value))
        preview = str(value[:3])[:60] if value else "[]"
    elif isinstance(value, dict):
        shape_or_len = f"{len(value)} keys"
        preview = str(sorted(list(value.keys()))[:5])[:60]
    else:
        try:
            shape_or_len = str(value.shape)
            preview = str(value.flat[:3].tolist())[:60]
        except AttributeError:
            preview = repr(value)[:60]

    return FieldDescriptor(
        key=key,
        python_type=python_type,
        shape_or_len=shape_or_len,
        preview=preview,
        stage=stage,
    )
