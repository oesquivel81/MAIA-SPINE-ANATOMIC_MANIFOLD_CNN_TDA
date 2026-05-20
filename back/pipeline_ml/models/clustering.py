from __future__ import annotations

from typing import Any


class ClusteringModel:
    name = "clustering"

    def predict(self, manifold_output: dict[str, Any]) -> dict[str, Any]:
        # Placeholder para clustering final sobre el embedding.
        embedding = manifold_output.get("manifold_embedding", [])
        cluster_id = 0 if len(embedding) == 0 else 1
        return {
            "model": self.name,
            "status": "ok",
            "cluster_id": cluster_id,
        }
