"""
BinaryCurveStage — inferencia CNN de 1 canal (binaria + curva).

Recibe del payload (producido por PreprocessingStage):
    payload["image"]:  np.ndarray [H, W]  uint8 o float32  normalizado

Agrega al payload:
    payload["binary_mask"]       np.ndarray [H,W]  uint8  {0,1}
    payload["curve_mask"]        np.ndarray [H,W]  uint8  {0,1}
    payload["binary_mask_path"]  str  ruta PNG guardada en outputs_dir
    payload["curve_mask_path"]   str  ruta PNG guardada en outputs_dir
    payload["binary_curve_meta"] dict  epoch, stage, best_val_loss del checkpoint
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch

from pipeline_ml.cnn_curve import FastBinaryCurveUNet, load_binary_curve_model
from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.stages.base import PipelineStage

# Umbral por defecto para binarizar la salida sigmoid
_THRESHOLD = 0.5


class BinaryCurveStage(PipelineStage):
    """Stage de inferencia CNN 1-canal: columna binaria + curva espinal."""

    name = "binary_curve"

    def __init__(self) -> None:
        self._model: FastBinaryCurveUNet | None = None
        self._device: torch.device | None = None

    # ------------------------------------------------------------------
    # Carga lazy del modelo (solo la primera vez que se ejecuta el stage)
    # ------------------------------------------------------------------

    def _load_model(self, checkpoint_path: str, logger: PipelineLogger) -> None:
        if self._model is not None:
            return

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"BinaryCurveStage: cargando checkpoint desde {checkpoint_path} en {self._device}")
        self._model = load_binary_curve_model(checkpoint_path, device=self._device)
        logger.info("BinaryCurveStage: modelo listo")

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(self, payload: dict[str, Any], context: PipelineContext, logger: PipelineLogger) -> dict[str, Any]:
        image: np.ndarray | None = payload.get("image")
        if image is None:
            raise ValueError("BinaryCurveStage: no hay imagen en el payload. Ejecuta PreprocessingStage primero.")

        # Ruta del checkpoint: context.metadata o fallback en work_dir
        checkpoint_path = context.metadata.get("binary_curve_model_path", "")
        if not checkpoint_path:
            raise ValueError(
                "BinaryCurveStage: falta 'binary_curve_model_path' en context.metadata. "
                "Configúralo en PipelinePaths.binary_curve_model_path"
            )

        # --- 1. Cargar modelo (lazy) ---
        self._load_model(checkpoint_path, logger)
        assert self._model is not None
        assert self._device is not None

        # --- 2. Preparar tensor de entrada ---
        tensor = self._image_to_tensor(image, self._device)
        logger.debug(f"BinaryCurveStage: tensor de entrada shape={tuple(tensor.shape)}, device={self._device}")

        # --- 3. Inferencia ---
        with torch.no_grad():
            out = self._model(tensor)

        binary_logits: torch.Tensor = out["binary"]   # [1,1,H,W]
        curve_logits:  torch.Tensor = out["curve"]    # [1,1,H,W]

        # --- 4. Postprocesar: sigmoid + umbral ---
        binary_prob = torch.sigmoid(binary_logits)[0, 0].cpu().numpy()  # [H,W] float
        curve_prob  = torch.sigmoid(curve_logits)[0, 0].cpu().numpy()   # [H,W] float

        binary_mask = (binary_prob >= _THRESHOLD).astype(np.uint8)
        curve_mask  = (curve_prob  >= _THRESHOLD).astype(np.uint8)

        logger.debug(
            f"BinaryCurveStage: binary coverage={binary_mask.mean()*100:.1f}%, "
            f"curve coverage={curve_mask.mean()*100:.1f}%"
        )

        # --- 5. Guardar máscaras en outputs_dir ---
        binary_mask_path = self._save_mask(binary_mask, "binary_mask.png", context, logger)
        curve_mask_path  = self._save_mask(curve_mask,  "curve_mask.png",  context, logger)

        # --- 6. Visualización (solo si plots_show=True) ---
        if context.metadata.get("plots_show", False):
            self._compare_masks(image, binary_mask, curve_mask)

        # --- 7. Actualizar payload ---
        payload["binary_mask"]       = binary_mask
        payload["curve_mask"]        = curve_mask
        payload["binary_mask_path"]  = str(binary_mask_path)
        payload["curve_mask_path"]   = str(curve_mask_path)
        payload["binary_curve_done"] = True

        return payload

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _image_to_tensor(image: np.ndarray, device: torch.device) -> torch.Tensor:
        """
        Convierte imagen numpy [H,W] o [H,W,C] → tensor [1,1,H,W] float32 [0,1].
        Si la imagen ya es float y sus valores están en [0,1] se usa tal cual.
        Si está en [0,255] se divide por 255.
        """
        # Convertir a escala de grises si es RGB/BGR
        if image.ndim == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        arr = image.astype(np.float32)
        if arr.max() > 1.0:
            arr = arr / 255.0

        # [H,W] → [1,1,H,W]
        tensor = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)
        return tensor.to(device)

    @staticmethod
    def _save_mask(
        mask: np.ndarray,
        filename: str,
        context: PipelineContext,
        logger: PipelineLogger,
    ) -> Path:
        """Guarda máscara uint8 {0,1} como PNG de 8 bits {0, 255} en outputs_dir."""
        path = context.outputs_dir / filename
        cv2.imwrite(str(path), mask * 255)
        logger.info(f"BinaryCurveStage: {filename} guardado en {path}")
        return path

    @staticmethod
    def _compare_masks(
        image: np.ndarray,
        binary_mask: np.ndarray,
        curve_mask: np.ndarray,
    ) -> None:
        """Visualización inline para Colab/Jupyter (solo si plots_show=True)."""
        import matplotlib.pyplot as plt  # lazy import

        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        axes[0].imshow(image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cmap="gray")
        axes[0].set_title("Imagen normalizada\n(PreprocessingStage output)")
        axes[0].axis("off")

        axes[1].imshow(binary_mask, cmap="gray", vmin=0, vmax=1)
        axes[1].set_title(f"Máscara binaria\ncoverage={binary_mask.mean()*100:.1f}%")
        axes[1].axis("off")

        axes[2].imshow(curve_mask, cmap="hot", vmin=0, vmax=1)
        axes[2].set_title(f"Máscara de curva\ncoverage={curve_mask.mean()*100:.1f}%")
        axes[2].axis("off")

        fig.suptitle("BinaryCurveStage — salida CNN", fontsize=13)
        plt.tight_layout()
        plt.show()
