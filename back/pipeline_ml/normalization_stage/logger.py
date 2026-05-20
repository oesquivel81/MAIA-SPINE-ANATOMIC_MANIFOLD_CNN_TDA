from __future__ import annotations

import logging
from typing import Any


def log_method_start(logger: logging.Logger, class_name: str, method_name: str, **kwargs: Any) -> None:
    details = ", ".join(f"{key}={value}" for key, value in kwargs.items() if value is not None)
    if details:
        logger.info("[START] %s.%s | %s", class_name, method_name, details)
        return
    logger.info("[START] %s.%s", class_name, method_name)
