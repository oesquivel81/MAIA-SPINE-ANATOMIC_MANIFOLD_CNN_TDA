"""
StudentPatchStage — inferencia del modelo StudentUNet1CH4Heads sobre los N parches
extraídos por CurvePatchStage.

Recibe del payload (producido por CurvePatchStage):
    payload["patches"]           list[np.ndarray]  float32/uint8  [H_i, W_i]
    payload["patch_meta"]        list[dict]        metadatos por parche del CSV manifest
    payload["curve_patch_done"]  bool True

Agrega al payload:
    payload["student_patch_dir"]  str            directorio raíz de salidas del stage
    payload["student_csv_path"]   str            ruta al CSV de métricas por parche×cabeza
    payload["student_outputs"]    list[dict]     por parche: patch_idx + 4 mapas prob float32 [224,224]
    payload["student_masks"]      list[dict]     por parche: patch_idx + 4 máscaras uint8 {0,1} [224,224]
    payload["student_done"]       bool True

Inferencia por parche:
    1. Resize a IMG_SIZE=224×224 (cv2.resize, interpolación INTER_LINEAR).
    2. Normalizar a float32 [0,1] (÷255 si uint8, clip si float).
    3. x = tensor [1,1,224,224].
    4. with torch.no_grad(): out = model(x).
    5. prob  = sigmoid(logits)[0, 0]  →  float32 [224,224].
    6. mask  = (prob >= THRESHOLD).astype(uint8).

Salidas en disco (outputs/student_patches/):
    patch_{i:02d}/
        input.png          parche redimensionado a 224×224 (referencia visual)
        binary.png         mapa de probabilidad binary (escala gris 0-255)
        boundary.png       mapa de probabilidad boundary
        intervertebral.png mapa de probabilidad intervertebral
        ordinal.png        mapa de probabilidad ordinal

    student_patch_manifest.csv   métricas por parche×cabeza

CSV columnas:
    patient_key, patch_idx, head,
    coverage_pct, prob_mean, prob_max, prob_min,
    output_path, crop_side

Visualización (solo si context.metadata["plots_show"] is True):
    _show_patch_grid():
        N filas × 5 columnas:
            col 0 : parche original (224×224, gray)
            col 1 : binary prob map  (hot)
            col 2 : boundary prob map  (coolwarm)
            col 3 : intervertebral prob map  (viridis)
            col 4 : ordinal prob map  (plasma)
        Título por celda de máscara: "Head  cov=XX.X%"

    _show_head_summary():
        4 paneles horizontales, uno por cabeza.
        Cada panel: collage de todos los parches de esa cabeza apilados en fila.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.stages.base import PipelineStage
from pipeline_ml.student_cnn import StudentUNet1CH4Heads, load_student_patch_model

# ──────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────
_IMG_SIZE: int = 224          # tamaño de entrada del modelo
_THRESHOLD: float = 0.5       # umbral para binarizar la salida sigmoid

_HEADS: tuple[str, ...] = ("binary", "boundary", "intervertebral", "ordinal")

_HEAD_CMAPS: dict[str, str] = {
    "binary": "hot",
    "boundary": "coolwarm",
    "intervertebral": "viridis",
    "ordinal": "plasma",
}


class StudentPatchStage(PipelineStage):
    """Inferencia StudentUNet1CH4Heads sobre parches de la curva espinal."""

    name = "student_patch"

    def __init__(self) -> None:
        self._model: StudentUNet1CH4Heads | None = None
        self._device: torch.device | None = None

    # ------------------------------------------------------------------
    # Carga lazy del modelo
    # ------------------------------------------------------------------

    def _load_model(self, checkpoint_path: str, logger: PipelineLogger) -> None:
        if self._model is not None:
            return
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"StudentPatchStage: cargando checkpoint desde {checkpoint_path} en {self._device}")
        self._model = load_student_patch_model(checkpoint_path, device=self._device)
        logger.info("StudentPatchStage: modelo listo")

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(
        self, payload: dict[str, Any], context: PipelineContext, logger: PipelineLogger
    ) -> dict[str, Any]:

        # ── Guardia: requerir CurvePatchStage ──────────────────────────
        if not payload.get("curve_patch_done"):
            logger.warn(
                "StudentPatchStage: 'curve_patch_done' no encontrado en el payload. "
                "Asegúrate de ejecutar CurvePatchStage antes."
            )
            payload["student_patch_skipped"] = True
            return payload

        patches: list[np.ndarray] = payload.get("patches", [])
        patch_meta: list[dict] = payload.get("patch_meta", [])

        if not patches:
            logger.warn("StudentPatchStage: lista de parches vacía. Saltando stage.")
            payload["student_patch_skipped"] = True
            return payload

        # ── Ruta del checkpoint ────────────────────────────────────────
        checkpoint_path = self._resolve_checkpoint(context, logger)
        if not checkpoint_path:
            logger.warn(
                "StudentPatchStage: no se encontró ruta del checkpoint. "
                "Pasa la ruta del .pt como segundo elemento de full_assets "
                "o configura paths.student_patch_model_path en el config JSON."
            )
            payload["student_patch_skipped"] = True
            return payload

        try:
            self._load_model(checkpoint_path, logger)
        except (FileNotFoundError, ValueError, RuntimeError, KeyError) as exc:
            logger.warn(f"StudentPatchStage: no se pudo cargar el modelo — {exc}")
            payload["student_patch_skipped"] = True
            return payload

        # ── Directorios de salida ──────────────────────────────────────
        patient_key: str = str(context.assets.full_name or "patient")
        out_root = context.work_dir / "outputs" / "student_patches"
        out_root.mkdir(parents=True, exist_ok=True)

        plots_show: bool = bool(context.metadata.get("plots_show", False))

        # ── Buffers de resultado ───────────────────────────────────────
        csv_rows: list[dict] = []
        student_outputs: list[dict] = []
        student_masks: list[dict] = []

        # Para visualización acumulada
        debug_inputs: list[np.ndarray] = []
        debug_probs: list[dict[str, np.ndarray]] = []

        assert self._model is not None
        assert self._device is not None

        for i, patch in enumerate(patches):
            patch_dir = out_root / f"patch_{i:02d}"
            patch_dir.mkdir(parents=True, exist_ok=True)

            meta = patch_meta[i] if i < len(patch_meta) else {}
            crop_side = int(meta.get("crop_side", patch.shape[0] if patch.ndim >= 1 else 0))

            # ── Preprocesar ───────────────────────────────────────────
            patch_224 = self._preprocess(patch)

            # ── Inferencia ────────────────────────────────────────────
            x = torch.from_numpy(patch_224[None, None]).to(self._device)
            with torch.no_grad():
                raw_out = self._model(x)

            probs: dict[str, np.ndarray] = {}
            masks: dict[str, np.ndarray] = {}
            for head in _HEADS:
                prob = torch.sigmoid(raw_out[head])[0, 0].cpu().numpy()  # [224,224] float32
                probs[head] = prob
                masks[head] = (prob >= _THRESHOLD).astype(np.uint8)

            # ── Guardar en disco ──────────────────────────────────────
            input_path = patch_dir / "input.png"
            cv2.imwrite(str(input_path), (patch_224 * 255).astype(np.uint8))

            head_paths: dict[str, str] = {}
            for head in _HEADS:
                img_u8 = (probs[head] * 255).clip(0, 255).astype(np.uint8)
                p = patch_dir / f"{head}.png"
                cv2.imwrite(str(p), img_u8)
                head_paths[head] = str(p)

            # ── Métricas ──────────────────────────────────────────────
            for head in _HEADS:
                prob = probs[head]
                cov = float(np.mean(prob >= _THRESHOLD)) * 100.0
                csv_rows.append({
                    "patient_key": patient_key,
                    "patch_idx": i,
                    "head": head,
                    "coverage_pct": round(cov, 4),
                    "prob_mean": round(float(prob.mean()), 6),
                    "prob_max": round(float(prob.max()), 6),
                    "prob_min": round(float(prob.min()), 6),
                    "output_path": head_paths[head],
                    "crop_side": crop_side,
                })

            student_outputs.append({"patch_idx": i, **{h: probs[h] for h in _HEADS}})
            student_masks.append({"patch_idx": i, **{h: masks[h] for h in _HEADS}})
            debug_inputs.append(patch_224)
            debug_probs.append(probs)

        # ── Guardar CSV ────────────────────────────────────────────────
        csv_path = out_root / "student_patch_manifest.csv"
        _fields = [
            "patient_key", "patch_idx", "head",
            "coverage_pct", "prob_mean", "prob_max", "prob_min",
            "output_path", "crop_side",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=_fields)
            w.writeheader()
            w.writerows(csv_rows)

        logger.info(
            f"StudentPatchStage: {len(patches)} parches procesados → {csv_path}"
        )

        # ── Visualizaciones ────────────────────────────────────────────
        if plots_show:
            self._show_patch_grid(debug_inputs, debug_probs, patient_key)
            self._show_head_summary(debug_inputs, debug_probs)

        # ── Payload ────────────────────────────────────────────────────
        payload["student_patch_dir"] = str(out_root)
        payload["student_csv_path"] = str(csv_path)
        payload["student_outputs"] = student_outputs
        payload["student_masks"] = student_masks
        payload["student_done"] = True
        return payload

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_checkpoint(
        self, context: PipelineContext, logger: PipelineLogger
    ) -> str:
        """Prioridad: assets.joblib_paths[1] → config metadata."""
        if len(context.assets.joblib_paths) > 1:
            path = context.assets.joblib_paths[1].strip()
            if path:
                return self._validate_path(path, context, logger)

        # Fallback: configuración explícita
        path = str(context.metadata.get("student_patch_model_path", "")).strip()
        if path:
            return self._validate_path(path, context, logger)

        return ""

    def _validate_path(
        self, path: str, context: PipelineContext, logger: PipelineLogger
    ) -> str:
        """Devuelve la ruta resuelta si existe, cadena vacía si no."""
        p = Path(path)
        if p.exists():
            return str(p)

        # Intentar resolver relativa al workspace_root
        ws_root = str(context.metadata.get("workspace_root", "")).strip()
        if ws_root:
            candidate = Path(ws_root) / path
            if candidate.exists():
                return str(candidate)

        logger.warn(f"StudentPatchStage: checkpoint no encontrado en '{path}'")
        return ""

    @staticmethod
    def _preprocess(patch: np.ndarray) -> np.ndarray:
        """Resize a 224×224 y normaliza a float32 [0,1]."""
        if patch.ndim == 3:
            patch = patch[:, :, 0]  # coger primer canal si tiene 3
        resized = cv2.resize(patch, (_IMG_SIZE, _IMG_SIZE), interpolation=cv2.INTER_LINEAR)
        if resized.dtype == np.uint8:
            return resized.astype(np.float32) / 255.0
        return resized.astype(np.float32).clip(0.0, 1.0)

    # ------------------------------------------------------------------
    # Visualizaciones
    # ------------------------------------------------------------------

    def _show_patch_grid(
        self,
        inputs: list[np.ndarray],
        all_probs: list[dict[str, np.ndarray]],
        patient_key: str,
    ) -> None:
        """
        Grid N × 5:  input | binary | boundary | intervertebral | ordinal.
        Cada celda de máscara incluye cobertura como subtitle.
        """
        import matplotlib.pyplot as plt

        n = len(inputs)
        cols = 1 + len(_HEADS)  # 5
        fig, axes = plt.subplots(n, cols, figsize=(cols * 2.4, n * 2.4))
        if n == 1:
            axes = axes[np.newaxis, :]

        col_titles = ["Input"] + list(_HEADS)
        for c, title in enumerate(col_titles):
            axes[0, c].set_title(title, fontsize=8, fontweight="bold")

        cmaps = ["gray"] + [_HEAD_CMAPS[h] for h in _HEADS]

        for r, (inp, probs) in enumerate(zip(inputs, all_probs)):
            axes[r, 0].imshow(inp, cmap="gray", vmin=0, vmax=1)
            axes[r, 0].set_ylabel(f"P{r}", fontsize=7)
            axes[r, 0].axis("off")

            for c, head in enumerate(_HEADS, start=1):
                prob = probs[head]
                cov = float(np.mean(prob >= _THRESHOLD)) * 100.0
                axes[r, c].imshow(prob, cmap=cmaps[c], vmin=0, vmax=1)
                axes[r, c].set_title(f"cov={cov:.1f}%", fontsize=6)
                axes[r, c].axis("off")

        fig.suptitle(f"StudentPatchStage — {patient_key}", fontsize=9)
        plt.tight_layout()
        plt.show()

    def _show_head_summary(
        self,
        inputs: list[np.ndarray],
        all_probs: list[dict[str, np.ndarray]],
    ) -> None:
        """
        4 filas (una por cabeza), cada fila con todos los parches en columnas.
        Permite comparar la respuesta de cada cabeza en todos los parches.
        """
        import matplotlib.pyplot as plt

        n = len(inputs)
        fig, axes = plt.subplots(len(_HEADS), n, figsize=(n * 2.2, len(_HEADS) * 2.2))
        if n == 1:
            axes = axes[:, np.newaxis]

        for r, head in enumerate(_HEADS):
            axes[r, 0].set_ylabel(head, fontsize=8, fontweight="bold", rotation=90)
            cmap = _HEAD_CMAPS[head]
            for c, probs in enumerate(all_probs):
                prob = probs[head]
                cov = float(np.mean(prob >= _THRESHOLD)) * 100.0
                axes[r, c].imshow(prob, cmap=cmap, vmin=0, vmax=1)
                axes[r, c].set_title(f"P{c}\n{cov:.0f}%", fontsize=6)
                axes[r, c].axis("off")

        fig.suptitle("Resumen por cabeza — StudentPatchStage", fontsize=9)
        plt.tight_layout()
        plt.show()
