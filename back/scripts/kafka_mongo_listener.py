from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import time

from kafka import KafkaConsumer
from pymongo import MongoClient


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    enabled = _as_bool(os.getenv("LISTENER_ENABLED", "true"), default=True)
    if not enabled:
        print("[listener] disabled via LISTENER_ENABLED")
        return

    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    kafka_pattern = os.getenv("KAFKA_TOPIC_PATTERN", r"^pipeline-stage\..+")
    kafka_group_id = os.getenv("KAFKA_GROUP_ID", "pipeline-stage-listener")
    auto_offset_reset = os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest")

    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017")
    mongo_db = os.getenv("MONGO_DB", "app_db")
    mongo_collection = os.getenv("MONGO_LISTENER_COLLECTION", "pipeline_stage_metrics")

    print(
        "[listener] starting",
        {
            "kafka_bootstrap": kafka_bootstrap,
            "kafka_pattern": kafka_pattern,
            "kafka_group_id": kafka_group_id,
            "mongo_uri": mongo_uri,
            "mongo_db": mongo_db,
            "mongo_collection": mongo_collection,
        },
    )

    topic_regex = re.compile(kafka_pattern)

    while True:
        try:
            mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            mongo_client.admin.command("ping")
            target_collection = mongo_client[mongo_db][mongo_collection]

            consumer = KafkaConsumer(
                bootstrap_servers=[x.strip() for x in kafka_bootstrap.split(",") if x.strip()],
                group_id=kafka_group_id,
                auto_offset_reset=auto_offset_reset,
                enable_auto_commit=True,
                value_deserializer=lambda b: json.loads(b.decode("utf-8")),
                consumer_timeout_ms=1000,
                request_timeout_ms=30000,
                session_timeout_ms=10000,
            )
            consumer.subscribe(pattern=topic_regex)
            print("[listener] connected to Kafka and Mongo")

            while True:
                polled = consumer.poll(timeout_ms=1000, max_records=200)
                for _tp, records in polled.items():
                    for record in records:
                        event = record.value if isinstance(record.value, dict) else {"raw": record.value}
                        doc = {
                            "source": "kafka_listener",
                            "received_at": _now_iso(),
                            "kafka": {
                                "topic": record.topic,
                                "partition": record.partition,
                                "offset": record.offset,
                                "timestamp": record.timestamp,
                                "key": record.key.decode("utf-8") if isinstance(record.key, bytes) else record.key,
                            },
                            "event": event,
                        }
                        target_collection.insert_one(doc)

        except Exception as exc:
            print(f"[listener] error: {exc}; retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
