from __future__ import annotations

from typing import Any


class CnnCurveModel:
    name = "cnn_curve"

    def predict(self, image: Any) -> dict[str, Any]:
        # Placeholder para el modelo real cnn_curve.
        return {
            "model": self.name,
            "status": "ok",
            "curve_features": [0.0, 1.0, 2.0],
        }
