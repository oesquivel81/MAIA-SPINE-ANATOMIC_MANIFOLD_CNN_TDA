from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TPayload = TypeVar("TPayload")
TContext = TypeVar("TContext")


class PipelineProcessor(ABC, Generic[TPayload, TContext]):
    """Generic processor contract for chain-of-responsibility pipelines."""

    def __init__(self) -> None:
        self._next: PipelineProcessor[TPayload, TContext] | None = None

    def set_next(
        self,
        next_processor: PipelineProcessor[TPayload, TContext],
    ) -> PipelineProcessor[TPayload, TContext]:
        self._next = next_processor
        return next_processor

    async def process(self, payload: TPayload, context: TContext) -> TPayload:
        processed_payload = await self.handle(payload, context)
        if self._next is None:
            return processed_payload
        return await self._next.process(processed_payload, context)

    @abstractmethod
    async def handle(self, payload: TPayload, context: TContext) -> TPayload:
        """Single processing step implemented by concrete processors."""
        raise NotImplementedError
