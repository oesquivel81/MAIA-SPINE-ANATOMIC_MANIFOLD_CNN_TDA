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

        # Ruta del checkpoint: prioridad 1 → assets.joblib_paths[0] (pasado en full_assets)
        #                       prioridad 2 → config binary_curve_model_path
        checkpoint_path = ""
        if context.assets.joblib_paths:
            checkpoint_path = context.assets.joblib_paths[0].strip()
        if not checkpoint_path:
            checkpoint_path = context.metadata.get("binary_curve_model_path", "").strip()

        # Intentar resolver la ruta si no existe tal cual
        if checkpoint_path:
            checkpoint_path = self._resolve_checkpoint_path(checkpoint_path, context, logger)

        # Si sigue vacía o no existe, saltar el stage sin explotar el pipeline
        if not checkpoint_path:
            logger.warn(
                "BinaryCurveStage: no se encontró ruta del checkpoint. "
                "Pasa la ruta del .pt como primer elemento de full_assets "
                "o configura paths.binary_curve_model_path en el config JSON. "
                "Stage saltado."
            )
            payload["binary_curve_skipped"] = True
            return payload

        if not Path(checkpoint_path).exists():
            logger.warn(
                f"BinaryCurveStage: checkpoint no encontrado en '{checkpoint_path}'. "
                "Verifica la ruta en paths.binary_curve_model_path. Stage saltado."
            )
            payload["binary_curve_skipped"] = True
            payload["binary_curve_checkpoint_path_tried"] = checkpoint_path
            return payload

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
            self._show_image(image, title="Imagen normalizada → entrada CNN")
            self._show_mask(binary_mask, title="Máscara binaria (salida CNN)", cmap="gray")
            self._show_mask(curve_mask,  title="Máscara de curva  (salida CNN)", cmap="hot")
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
    def _resolve_checkpoint_path(
        checkpoint_path: str,
        context: PipelineContext,
        logger: PipelineLogger,
    ) -> str:
        """
        Intenta resolver la ruta del checkpoint:
        1. Tal cual (absoluta).
        2. Relativa al workspace_root del config.
        3. Relativa al work_dir del contexto (work_dir/../../..)
        Devuelve la primera ruta que exista, o la original si ninguna funciona.
        """
        from pathlib import Path as _Path

        candidates = [checkpoint_path]

        workspace_root = context.metadata.get("workspace_root", "")
        if workspace_root:
            # quitar '/' inicial del path para hacer join correcto
            rel = checkpoint_path.lstrip("/")
            candidates.append(str(_Path(workspace_root) / rel))

        for candidate in candidates:
            if _Path(candidate).exists():
                if candidate != checkpoint_path:
                    logger.info(f"BinaryCurveStage: ruta resuelta → {candidate}")
                return candidate

        # Ninguna encontrada: devolver la original para que el caller la rechace
        logger.warn(
            f"BinaryCurveStage: probé las siguientes rutas y ninguna existe:\n"
            + "\n".join(f"  - {c}" for c in candidates)
        )
        return checkpoint_path

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
        """Guarda máscara uint8 {0,1} como PNG de 8 bits {0,255} en outputs_dir/cnn_curve/."""
        # Subcarpeta dedicada para predicciones de este stage
        out_dir = context.outputs_dir / "cnn_curve"
        out_dir.mkdir(parents=True, exist_ok=True)

        path = out_dir / filename

        # Forzar dtype uint8 explicitamente — numpy puede elevar uint8*255 a int64
        # lo que hace que cv2.imwrite falle silenciosamente
        img_to_write = (mask.astype(np.uint8) * 255).astype(np.uint8)

        ok = cv2.imwrite(str(path), img_to_write)
        if ok:
            logger.info(f"BinaryCurveStage: {filename} guardado en {path}")
        else:
            logger.warn(
                f"BinaryCurveStage: cv2.imwrite falló para {path}. "
                f"dtype={img_to_write.dtype}, shape={img_to_write.shape}, "
                f"max={img_to_write.max()}"
            )
        return path

    @staticmethod
    def _show_image(image: np.ndarray, title: str = "Imagen de entrada CNN") -> None:
        """
        Muestra la imagen de entrada (escala de grises) con sus estadísticas.
        Solo se invoca cuando plots_show=True.
        """
        import matplotlib.pyplot as plt  # lazy import

        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        arr = gray.astype(np.float32)

        stats_lines = [
            f"shape={gray.shape}  dtype={gray.dtype}",
            f"mean={arr.mean():.2f}  std={arr.std():.2f}",
            f"min={arr.min():.0f}  max={arr.max():.0f}",
            f"p5={np.percentile(arr,5):.1f}  p95={np.percentile(arr,95):.1f}",
        ]

        fig, ax = plt.subplots(figsize=(5, 6))
        ax.imshow(gray, cmap="gray", vmin=0, vmax=255)
        ax.set_title(title, fontsize=11, pad=10)
        ax.axis("off")
        fig.text(
            0.5, 0.02,
            "\n".join(stats_lines),
            ha="center", va="bottom",
            fontsize=8,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.4", fc="#f5f5f5", ec="#cccccc"),
        )
        plt.tight_layout(rect=[0, 0.12, 1, 1])
        plt.show()

    @staticmethod
    def _show_mask(mask: np.ndarray, title: str, cmap: str = "gray") -> None:
        """
        Muestra una máscara binaria {0,1} con sus estadísticas de cobertura.
        Solo se invoca cuando plots_show=True.
        """
        import matplotlib.pyplot as plt  # lazy import

        coverage = mask.mean() * 100
        n_pixels = int(mask.sum())
        total = mask.size

        stats_lines = [
            f"shape={mask.shape}  dtype={mask.dtype}",
            f"coverage={coverage:.2f}%  ({n_pixels:,} / {total:,} px)",
            f"valores únicos={np.unique(mask).tolist()}",
        ]

        fig, ax = plt.subplots(figsize=(5, 6))
        ax.imshow(mask, cmap=cmap, vmin=0, vmax=1)
        ax.set_title(title, fontsize=11, pad=10)
        ax.axis("off")
        fig.text(
            0.5, 0.02,
            "\n".join(stats_lines),
            ha="center", va="bottom",
            fontsize=8,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.4", fc="#f5f5f5", ec="#cccccc"),
        )
        plt.tight_layout(rect=[0, 0.10, 1, 1])
        plt.show()

    @staticmethod
    def _compare_masks(
        image: np.ndarray,
        binary_mask: np.ndarray,
        curve_mask: np.ndarray,
    ) -> None:
        """
        Grid 1×3: imagen de entrada | máscara binaria | máscara de curva.
        Cada panel muestra sus stats individuales.
        Solo se invoca cuando plots_show=True.
        """
        import matplotlib.pyplot as plt  # lazy import

        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        arr = gray.astype(np.float32)

        fig, axes = plt.subplots(1, 3, figsize=(16, 6))

        # --- Panel 0: imagen normalizada ---
        axes[0].imshow(gray, cmap="gray", vmin=0, vmax=255)
        axes[0].set_title(
            "Imagen normalizada\n(PreprocessingStage output)",
            fontsize=10,
        )
        axes[0].axis("off")
        axes[0].set_xlabel(
            f"shape={gray.shape}\n"
            f"mean={arr.mean():.1f}  std={arr.std():.1f}\n"
            f"p5={np.percentile(arr,5):.1f}  p95={np.percentile(arr,95):.1f}",
            fontsize=7.5,
            labelpad=6,
        )

        # --- Panel 1: máscara binaria ---
        b_cov = binary_mask.mean() * 100
        axes[1].imshow(binary_mask, cmap="gray", vmin=0, vmax=1)
        axes[1].set_title(
            f"Máscara binaria\ncoverage={b_cov:.1f}%",
            fontsize=10,
        )
        axes[1].axis("off")
        axes[1].set_xlabel(
            f"shape={binary_mask.shape}  dtype={binary_mask.dtype}\n"
            f"píxeles activos={int(binary_mask.sum()):,} / {binary_mask.size:,}",
            fontsize=7.5,
            labelpad=6,
        )

        # --- Panel 2: máscara de curva ---
        c_cov = curve_mask.mean() * 100
        axes[2].imshow(curve_mask, cmap="hot", vmin=0, vmax=1)
        axes[2].set_title(
            f"Máscara de curva\ncoverage={c_cov:.1f}%",
            fontsize=10,
        )
        axes[2].axis("off")
        axes[2].set_xlabel(
            f"shape={curve_mask.shape}  dtype={curve_mask.dtype}\n"
            f"píxeles activos={int(curve_mask.sum()):,} / {curve_mask.size:,}",
            fontsize=7.5,
            labelpad=6,
        )

        fig.suptitle("BinaryCurveStage — salida CNN", fontsize=13, y=1.01)
        plt.tight_layout()
        plt.show()
