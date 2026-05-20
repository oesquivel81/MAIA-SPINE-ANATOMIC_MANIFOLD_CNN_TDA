from __future__ import annotations

from typing import Any


class EventBridge:
    def __init__(self, kafka_enabled: bool, lambda_enabled: bool, kafka_topic: str, lambda_name: str) -> None:
        self.kafka_enabled = kafka_enabled
        self.lambda_enabled = lambda_enabled
        self.kafka_topic = kafka_topic
        self.lambda_name = lambda_name

    def publish_progress(self, event: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {"kafka": "disabled", "lambda": "disabled"}
        if self.kafka_enabled:
            out["kafka"] = f"queued:{self.kafka_topic}"
        if self.lambda_enabled:
            out["lambda"] = f"queued:{self.lambda_name}"
        out["event_type"] = event.get("type", "progress")
        return out
