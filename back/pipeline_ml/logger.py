from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class PipelineLogger:
    enabled: bool = True
    verbose: bool = True

    def info(self, message: str) -> None:
        if self.enabled:
            print(f"[PIPELINE][INFO] {message}")

    def debug(self, message: str) -> None:
        if self.enabled and self.verbose:
            print(f"[PIPELINE][DEBUG] {message}")

    def warn(self, message: str) -> None:
        if self.enabled:
            print(f"[PIPELINE][WARN] {message}")


def timed_step(label: str, func, logger: PipelineLogger):
    start = time.perf_counter()
    result = func()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    logger.debug(f"Paso '{label}' completo en {elapsed_ms:.2f} ms")
    return result, elapsed_ms
