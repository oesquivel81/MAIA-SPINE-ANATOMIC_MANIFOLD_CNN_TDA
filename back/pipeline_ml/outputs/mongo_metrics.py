from __future__ import annotations

from typing import Any


class MongoMetricsWriter:
    def __init__(self, enabled: bool, database: str, collection: str) -> None:
        self.enabled = enabled
        self.database = database
        self.collection = collection

    def write_metrics(self, metrics: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled"}

        # Placeholder para integrar repositorio/cliente de Mongo.
        return {
            "status": "queued",
            "database": self.database,
            "collection": self.collection,
            "keys": sorted(list(metrics.keys())),
        }
