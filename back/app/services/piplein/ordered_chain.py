from __future__ import annotations

from collections import OrderedDict

import numpy as np

from app.services.pipeline_processor import PipelineProcessor
from app.services.piplein.resize_image_pipeline import ResizeImagePipeline
from app.services.piplein.types import NormalizationPipelineContext


def build_ordered_pipeline() -> OrderedDict[str, PipelineProcessor[np.ndarray, NormalizationPipelineContext]]:
    ordered_map: OrderedDict[str, PipelineProcessor[np.ndarray, NormalizationPipelineContext]] = OrderedDict()
    ordered_map[ResizeImagePipeline.name] = ResizeImagePipeline()
    return ordered_map


def wire_pipeline_chain(
    ordered_map: OrderedDict[str, PipelineProcessor[np.ndarray, NormalizationPipelineContext]],
) -> PipelineProcessor[np.ndarray, NormalizationPipelineContext]:
    processors = list(ordered_map.values())
    if not processors:
        raise ValueError("La cadena de responsabilidad no tiene implementaciones")

    for idx in range(len(processors) - 1):
        processors[idx].set_next(processors[idx + 1])

    return processors[0]
