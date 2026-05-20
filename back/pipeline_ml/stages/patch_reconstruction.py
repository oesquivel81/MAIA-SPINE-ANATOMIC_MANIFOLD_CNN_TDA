"""
PatchReconstructionStage — reconstruye mapas full-size por paciente a partir de
los parches inferidos por StudentPatchStage.

Equivalente al BLOQUE 2 del cuaderno (process_patient_combined_frequency_class).

Recibe del payload (producido por StudentPatchStage):
    payload["student_outputs"]       list[dict]  por parche: patch_idx + 4 mapas prob float32 [224,224]
    payload["patch_meta"]            list[dict]  metadatos de coordenadas por parche (CurvePatchStage)
    payload["image"]                 ndarray     imagen normalizada — usada para obtener H, W
    payload["student_done"]          bool True

Agrega al payload:
    payload["recon_dir"]             str         directorio raíz de salidas
    payload["recon_maps"]            dict[str, ndarray]  float32 [H, W] por cabeza (promedio ponderado)
    payload["recon_masks"]           dict[str, ndarray]  uint8 {0,1} [H, W] por cabeza (≥ threshold)
    payload["freq_maps"]             dict[str, ndarray]  float32 [H, W] fracción de parches que votan +
    payload["coverage_map"]          ndarray     float32 [H, W] fracción de parches que cubren cada px
    payload["support_map"]           ndarray     uint8 {0,1} [H, W]  binary>0.30 & coverage>0
    payload["combined_signal"]       ndarray     float32 [H, W]  señal estructural ponderada
                                                 = (0.55*boundary + 0.85*intervertebral + 0.15*ordinal) * support
    payload["recon_csv_path"]        str         ruta al CSV de métricas por cabeza
    payload["patch_reconstruction_done"] bool True

Señal combinada:
    binary actúa como soporte (umbral relajado 0.30) — define dónde hay estructura.
    boundary e intervertebral son las señales estructurales principales.
    ordinal aporta información de orden secuencial con peso menor.
    La suma de pesos es 1.55; el resultado se clipea a [0, 1] solo para PNG.

Algoritmo de reconstrucción (por cabeza):
    1. Crear acumuladores: accum[H,W] y count[H,W] a cero.
    2. Para cada parche i:
        a. pred_224 = student_outputs[i][head]                  →  float32 [224, 224]
        b. Redimensionar a [crop_side, crop_side] (cv2.resize, INTER_LINEAR).
        c. Extraer región válida (sin padding):
               py1 = pad_top
               py2 = crop_side - pad_bottom  (o crop_side si pad_bottom == 0)
               px1 = pad_left
               px2 = crop_side - pad_right   (o crop_side si pad_right  == 0)
               pred_valid = pred_cs[py1:py2, px1:px2]
        d. Coordenadas en imagen origen:
               iy1 = crop_y1 + pad_top,   iy2 = crop_y2 - pad_bottom
               ix1 = crop_x1 + pad_left,  ix2 = crop_x2 - pad_right
               → recortados al rango [0, H) × [0, W).
        e. Acumular: accum[iy1c:iy2c, ix1c:ix2c] += pred_valid[offset...]
                     count[iy1c:iy2c, ix1c:ix2c] += 1
    3. recon[head] = accum / max(count, 1)

Análisis de frecuencia:
    - freq_map[head]: fracción de parches superpuestos que votan ≥ threshold.
    - coverage_map:   fracción de los N parches totales que cubren cada pixel.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .base import PipelineStage
from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger

# ──────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────
_HEADS: tuple[str, ...] = ("binary", "boundary", "intervertebral", "ordinal")
_THRESHOLD: float = 0.5
_IMG_SIZE: int = 224   # tamaño de salida del StudentUNet


class PatchReconstructionStage(PipelineStage):
    """
    Reconstruye los mapas de predicción full-size (H×W de la imagen normalizada)
    combinando los N parches inferidos por StudentPatchStage.

    Equivalente a ``process_patient_combined_frequency_class`` del cuaderno.
    """

    name = "patch_reconstruction"

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(
        self, payload: dict[str, Any], context: PipelineContext, logger: PipelineLogger
    ) -> dict[str, Any]:

        # ── Guardia: requiere StudentPatchStage ────────────────────────
        if not payload.get("student_done"):
            logger.warn(
                "PatchReconstructionStage: 'student_done' no encontrado. "
                "Asegúrate de ejecutar StudentPatchStage antes."
            )
            payload["patch_reconstruction_skipped"] = True
            return payload

        student_outputs: list[dict] = payload.get("student_outputs", [])
        patch_meta: list[dict] = payload.get("patch_meta", [])

        if not student_outputs:
            logger.warn("PatchReconstructionStage: student_outputs vacío. Saltando.")
            payload["patch_reconstruction_skipped"] = True
            return payload

        # ── Dimensiones de la imagen origen ───────────────────────────
        image: np.ndarray = payload["image"]
        H, W = image.shape[:2]

        # ── Directorios de salida ──────────────────────────────────────
        out_root = context.work_dir / "outputs" / "patch_reconstruction"
        freq_root = out_root / "frequency_analysis"
        out_root.mkdir(parents=True, exist_ok=True)
        freq_root.mkdir(parents=True, exist_ok=True)

        plots_show: bool = bool(context.metadata.get("plots_show", False))

        # ── Reconstrucción ─────────────────────────────────────────────
        recon_maps, recon_masks, freq_maps, coverage_map = self._reconstruct(
            student_outputs=student_outputs,
            patch_meta=patch_meta,
            H=H,
            W=W,
        )

        # ── Guardar imágenes ───────────────────────────────────────────
        recon_paths: dict[str, str] = {}
        mask_paths: dict[str, str] = {}
        freq_paths: dict[str, str] = {}

        for head in _HEADS:
            # Mapa de probabilidad promediado
            rp = out_root / f"{head}_recon.png"
            cv2.imwrite(str(rp), (recon_maps[head] * 255).clip(0, 255).astype(np.uint8))
            recon_paths[head] = str(rp)

            # Máscara binarizada
            mp = out_root / f"{head}_mask.png"
            cv2.imwrite(str(mp), recon_masks[head] * 255)
            mask_paths[head] = str(mp)

            # Mapa de frecuencia (votos)
            fp = freq_root / f"{head}_freq.png"
            cv2.imwrite(str(fp), (freq_maps[head] * 255).clip(0, 255).astype(np.uint8))
            freq_paths[head] = str(fp)

        # Coverage map
        cov_p = out_root / "coverage_map.png"
        cv2.imwrite(str(cov_p), (coverage_map * 255).clip(0, 255).astype(np.uint8))

        logger.info(
            f"PatchReconstructionStage: mapas reconstruidos ({H}×{W}) → {out_root}"
        )

        # ── CSV de métricas ────────────────────────────────────────────
        csv_path = out_root / "reconstruction_manifest.csv"
        csv_rows = self._build_csv(recon_maps, freq_maps, coverage_map, recon_paths, freq_paths)
        _fields = [
            "head", "recon_coverage_pct", "recon_prob_mean", "recon_prob_max",
            "freq_coverage_pct", "freq_prob_mean",
            "global_coverage_pct", "recon_path", "freq_path",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=_fields)
            w.writeheader()
            w.writerows(csv_rows)

        # ── Señal combinada ────────────────────────────────────────────
        support_map, combined_signal = self._compute_combined_signal(
            recon_maps=recon_maps,
            coverage_map=coverage_map,
        )

        sp = out_root / "support_map.png"
        cv2.imwrite(str(sp), support_map * 255)

        cs_p = out_root / "combined_signal.png"
        cv2.imwrite(str(cs_p), (combined_signal.clip(0.0, 1.0) * 255).astype(np.uint8))

        logger.info(
            f"PatchReconstructionStage: señal combinada guardada → {cs_p}"
        )

        # ── Visualizaciones ────────────────────────────────────────────
        if plots_show:
            self._show_reconstruction(
                image, recon_maps, freq_maps, coverage_map,
                support_map, combined_signal,
            )

        # ── Payload ────────────────────────────────────────────────────
        payload["recon_dir"] = str(out_root)
        payload["recon_maps"] = recon_maps
        payload["recon_masks"] = recon_masks
        payload["freq_maps"] = freq_maps
        payload["coverage_map"] = coverage_map
        payload["support_map"] = support_map
        payload["combined_signal"] = combined_signal
        payload["recon_csv_path"] = str(csv_path)
        payload["patch_reconstruction_done"] = True
        return payload

    # ------------------------------------------------------------------
    # Algoritmo central
    # ------------------------------------------------------------------

    @staticmethod
    def _reconstruct(
        student_outputs: list[dict],
        patch_meta: list[dict],
        H: int,
        W: int,
    ) -> tuple[
        dict[str, np.ndarray],  # recon_maps
        dict[str, np.ndarray],  # recon_masks
        dict[str, np.ndarray],  # freq_maps
        np.ndarray,             # coverage_map
    ]:
        """
        Reconstruye probabilidad media y mapa de frecuencia de votos
        para cada cabeza sobre la imagen completa (H × W).
        """
        n_patches = len(student_outputs)

        # Acumuladores por cabeza
        accum:      dict[str, np.ndarray] = {h: np.zeros((H, W), np.float32) for h in _HEADS}
        count:      dict[str, np.ndarray] = {h: np.zeros((H, W), np.int32)   for h in _HEADS}
        vote_accum: dict[str, np.ndarray] = {h: np.zeros((H, W), np.float32) for h in _HEADS}
        count_global = np.zeros((H, W), np.int32)  # parches que cubren cada píxel

        for out in student_outputs:
            idx = out["patch_idx"]
            meta = patch_meta[idx] if idx < len(patch_meta) else {}

            crop_side   = int(meta.get("crop_side", _IMG_SIZE))
            pad_top     = int(meta.get("pad_top",    0))
            pad_bottom  = int(meta.get("pad_bottom", 0))
            pad_left    = int(meta.get("pad_left",   0))
            pad_right   = int(meta.get("pad_right",  0))
            crop_y1     = int(meta.get("crop_y1",    0))
            crop_y2     = int(meta.get("crop_y2",    crop_side))
            crop_x1     = int(meta.get("crop_x1",    0))
            crop_x2     = int(meta.get("crop_x2",    crop_side))

            # Coordenadas válidas (sin padding) en imagen origen
            iy1 = crop_y1 + pad_top
            iy2 = crop_y2 - pad_bottom if pad_bottom > 0 else crop_y2
            ix1 = crop_x1 + pad_left
            ix2 = crop_x2 - pad_right  if pad_right  > 0 else crop_x2

            # Recortar a límites de imagen
            iy1c = max(0, iy1);  iy2c = min(H, iy2)
            ix1c = max(0, ix1);  ix2c = min(W, ix2)

            if iy2c <= iy1c or ix2c <= ix1c:
                continue  # parche completamente fuera de la imagen

            # Región correspondiente dentro de pred_valid
            dy1 = iy1c - iy1;  dy2 = dy1 + (iy2c - iy1c)
            dx1 = ix1c - ix1;  dx2 = dx1 + (ix2c - ix1c)

            # Actualizar cobertura global (compartida por todas las cabezas)
            count_global[iy1c:iy2c, ix1c:ix2c] += 1

            for head in _HEADS:
                pred_224 = out[head]  # float32 [224, 224]

                # Redimensionar al tamaño original del parche
                pred_cs = cv2.resize(
                    pred_224, (crop_side, crop_side),
                    interpolation=cv2.INTER_LINEAR,
                )

                # Extraer región sin padding
                py1 = pad_top
                py2 = crop_side - pad_bottom if pad_bottom > 0 else crop_side
                px1 = pad_left
                px2 = crop_side - pad_right  if pad_right  > 0 else crop_side

                pred_valid = pred_cs[py1:py2, px1:px2]

                # Sub-región que cae dentro de la imagen (tras clamp)
                region = pred_valid[dy1:dy2, dx1:dx2]

                accum[head][iy1c:iy2c, ix1c:ix2c]      += region
                count[head][iy1c:iy2c, ix1c:ix2c]      += 1
                vote_accum[head][iy1c:iy2c, ix1c:ix2c] += (region >= _THRESHOLD).astype(np.float32)

        # Promediar
        recon_maps:  dict[str, np.ndarray] = {}
        recon_masks: dict[str, np.ndarray] = {}
        freq_maps:   dict[str, np.ndarray] = {}

        for head in _HEADS:
            denom = np.maximum(count[head], 1).astype(np.float32)
            recon_maps[head]  = accum[head] / denom
            recon_masks[head] = (recon_maps[head] >= _THRESHOLD).astype(np.uint8)
            freq_maps[head]   = vote_accum[head] / denom

        coverage_map = count_global.astype(np.float32) / max(n_patches, 1)

        return recon_maps, recon_masks, freq_maps, coverage_map

    @staticmethod
    def _compute_combined_signal(
        recon_maps: dict[str, np.ndarray],
        coverage_map: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Genera la señal estructural combinada a partir de las cabezas reconstruidas.

        ``binary`` actúa como soporte con umbral relajado (> 0.30): define
        los píxeles donde existe estructura espinal visible.
        ``boundary`` e ``intervertebral`` son las señales estructurales
        principales (pesos altos). ``ordinal`` aporta información de orden
        con peso menor.

        Returns:
            support_map:     uint8 {0,1}  — máscara de soporte
            combined_signal: float32      — señal ponderada (puede superar 1.0
                                            ligeramente; clipear al guardar PNG)
        """
        binary_n        = recon_maps["binary"]
        boundary_n      = recon_maps["boundary"]
        inter_n         = recon_maps["intervertebral"]
        ordinal_n       = recon_maps["ordinal"]

        support = ((binary_n > 0.30) & (coverage_map > 0)).astype(np.uint8)

        signal_weighted = (
            0.55 * boundary_n +
            0.85 * inter_n    +
            0.15 * ordinal_n
        ) * support

        return support, signal_weighted.astype(np.float32)

    # ------------------------------------------------------------------
    # Métricas CSV
    # ------------------------------------------------------------------

    @staticmethod
    def _build_csv(
        recon_maps: dict[str, np.ndarray],
        freq_maps:  dict[str, np.ndarray],
        coverage_map: np.ndarray,
        recon_paths: dict[str, str],
        freq_paths:  dict[str, str],
    ) -> list[dict]:
        rows = []
        global_cov = float(np.mean(coverage_map > 0)) * 100.0
        for head in _HEADS:
            rm = recon_maps[head]
            fm = freq_maps[head]
            rows.append({
                "head":               head,
                "recon_coverage_pct": round(float(np.mean(rm >= _THRESHOLD)) * 100, 4),
                "recon_prob_mean":    round(float(rm.mean()), 6),
                "recon_prob_max":     round(float(rm.max()),  6),
                "freq_coverage_pct":  round(float(np.mean(fm >= _THRESHOLD)) * 100, 4),
                "freq_prob_mean":     round(float(fm.mean()), 6),
                "global_coverage_pct": round(global_cov, 4),
                "recon_path":         recon_paths[head],
                "freq_path":          freq_paths[head],
            })
        return rows

    # ------------------------------------------------------------------
    # Perfil vertical
    # ------------------------------------------------------------------

    @staticmethod
    def _profile_from_maps(
        boundary: np.ndarray,
        inter: np.ndarray,
        binary: np.ndarray | None = None,
    ) -> dict[str, np.ndarray]:
        """
        Perfil vertical de las señales estructurales proyectando sobre el eje de filas.

        Parameters
        ----------
        boundary : float32 [H, W]  mapa de bordes vertebrales reconstruido.
        inter    : float32 [H, W]  mapa intervertebral reconstruido.
        binary   : float32 [H, W]  máscara anatómica (opcional). Si se omite se
                                   asume cobertura total.

        Returns
        -------
        dict con:
            "boundary_profile"  float32 [H]  perfil vertical normalizado [0,1]
            "inter_profile"     float32 [H]  perfil vertical normalizado [0,1]
            "combined_profile"  float32 [H]  perfil vertical normalizado [0,1]
            "combined_map"      float32 [H,W] mapa combinado ponderado, clipeado [0,1]
        """
        if binary is None:
            binary = np.ones_like(boundary, dtype=np.float32)

        support = (np.clip(binary, 0.0, 1.0) > 0.30).astype(np.float32)

        boundary_w = boundary * support
        inter_w    = inter    * support

        boundary_profile = boundary_w.mean(axis=1)
        inter_profile    = inter_w.mean(axis=1)

        # intervertebral pesa más: marca gaps/espacios entre vértebras
        combined = np.clip(0.55 * boundary_w + 0.85 * inter_w, 0.0, 1.0)
        combined_profile = combined.mean(axis=1)

        def _norm01(v: np.ndarray) -> np.ndarray:
            v = np.asarray(v, dtype=np.float32)
            vmin, vmax = v.min(), v.max()
            if vmax > vmin:
                return (v - vmin) / (vmax - vmin + 1e-8)
            return np.zeros_like(v)

        return {
            "boundary_profile": _norm01(boundary_profile),
            "inter_profile":    _norm01(inter_profile),
            "combined_profile": _norm01(combined_profile),
            "combined_map":     combined,
        }

    # ------------------------------------------------------------------
    # Visualización
    # ------------------------------------------------------------------

    def _show_reconstruction(
        self,
        image: np.ndarray,
        recon_maps: dict[str, np.ndarray],
        freq_maps:  dict[str, np.ndarray],
        coverage_map: np.ndarray,
        support_map: np.ndarray,
        combined_signal: np.ndarray,
    ) -> None:
        """
        Grid 3 filas × (1 + N_heads) columnas:
          fila 0: imagen  | binary  | boundary | intervertebral | ordinal
          fila 1: coverage| freq_b  | freq_bo  | freq_inter     | freq_ord
          fila 2: support | combined_signal (span 4 cols)
        """
        import matplotlib.pyplot as plt

        ncols = 1 + len(_HEADS)  # 5
        fig, axes = plt.subplots(3, ncols, figsize=(ncols * 2.8, 9))

        # ── Fila 0: reconstrucción media por cabeza ────────────────────
        axes[0, 0].imshow(image if image.ndim == 2 else image[:, :, 0], cmap="gray")
        axes[0, 0].set_title("Imagen", fontsize=8, fontweight="bold")
        axes[0, 0].axis("off")

        for j, head in enumerate(_HEADS, start=1):
            rm = recon_maps[head]
            axes[0, j].imshow(rm, cmap="gray_r", vmin=0, vmax=1)
            axes[0, j].set_title(
                f"{head}\ncov={np.mean(rm >= _THRESHOLD)*100:.1f}%",
                fontsize=7,
            )
            axes[0, j].axis("off")

        # ── Fila 1: análisis de frecuencia ─────────────────────────────
        axes[1, 0].imshow(coverage_map, cmap="gray_r", vmin=0, vmax=1)
        axes[1, 0].set_title(
            f"Cobertura\nmean={coverage_map.mean():.2f}",
            fontsize=7,
        )
        axes[1, 0].axis("off")

        for j, head in enumerate(_HEADS, start=1):
            fm = freq_maps[head]
            axes[1, j].imshow(fm, cmap="gray_r", vmin=0, vmax=1)
            axes[1, j].set_title(
                f"freq_{head}\nmean={fm.mean():.2f}",
                fontsize=7,
            )
            axes[1, j].axis("off")

        # ── Fila 2: soporte y señal combinada ──────────────────────────
        axes[2, 0].imshow(support_map, cmap="gray_r", vmin=0, vmax=1)
        axes[2, 0].set_title(
            f"Soporte\n(binary>0.30)\ncov={support_map.mean()*100:.1f}%",
            fontsize=7,
        )
        axes[2, 0].axis("off")

        # Señal combinada ocupa las 4 columnas restantes de la fila 2
        # Se muestra en la columna 1; las 2-4 se ocultan
        vmax_cs = float(combined_signal.max()) or 1.0
        axes[2, 1].imshow(combined_signal, cmap="gray_r", vmin=0, vmax=vmax_cs)
        axes[2, 1].set_title(
            f"Señal combinada\n0.55·bound+0.85·inter+0.15·ord\nmax={vmax_cs:.2f}",
            fontsize=7,
        )
        axes[2, 1].axis("off")

        for j in range(2, ncols):
            axes[2, j].axis("off")

        fig.suptitle("PatchReconstructionStage — mapas full-size", fontsize=9)
        plt.tight_layout()
        plt.show()
