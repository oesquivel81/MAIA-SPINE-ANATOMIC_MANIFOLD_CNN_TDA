"""
CurvePatchStage — extracción de parches dinámicos alineados a la curva espinal.

Recibe del payload (producido por CurveRefinementStage):
    payload["image"]        np.ndarray [H, W]  uint8 o float32  imagen normalizada
    payload["binary_mask"]  np.ndarray [H, W]  uint8  {0, 1}
    payload["dp_ys"]        np.ndarray [N]     int32   coordenadas Y de la curva DP
    payload["dp_xs"]        np.ndarray [N]     float32 coordenadas X de la curva DP
    payload["dp_mask"]      np.ndarray [H, W]  uint8  {0, 1}   máscara de curva DP

Agrega al payload:
    payload["patch_dir"]         str   ruta al directorio raíz de parches
    payload["patch_csv_path"]    str   ruta al CSV manifest
    payload["patch_count"]       int   número de parches generados
    payload["patches"]           list[np.ndarray]  parches imagen float32 [H_i, W_i]
    payload["patch_meta"]        list[dict]        metadatos por parche (mismas cols que CSV)
    payload["curve_patch_done"]  bool  True

Algoritmo (fiel al BLOQUE H del cuaderno Colab):
    1. Construye la curva en espacio full-res desde dp_ys/dp_xs (ya están en full-res).
    2. Segmenta la curva en N_PATCHES segmentos equiponderados con np.linspace.
    3. Para cada segmento:
       a. Centro (cy, cx) = mediana de los puntos del segmento.
       b. seg_h  = rango vertical del segmento.
       c. local_width = ancho medio de la máscara binaria en ese rango de filas.
       d. side = max(min_side, SEG_H_FACTOR × seg_h, WIDTH_FACTOR × local_width),
                 recortado a max_side.
       e. crop_square_dynamic() → padding y recorte cuadrado centrado en (cy, cx).
       f. Guarda PNG imagen, PNG binario, PNG curva en subdirectorios.
       g. Añade fila al manifest.
    4. Guarda CSV con todas las columnas de metadatos.

Salida en disco:
    outputs/curve_patches/
        images/         patch_00.png … patch_07.png
        binary/         patch_00_binary.png …
        curve/          patch_00_curve.png …
        curve_patch_manifest.csv

Visualización (solo si context.metadata["plots_show"] is True):
    _show_patch_grid(): N subplots con imagen + overlay binaria + overlay curva.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.stages.base import PipelineStage

# ──────────────────────────────────────────────────────────────
# Hiperparámetros (idénticos al Colab BLOQUE H)
# ──────────────────────────────────────────────────────────────
_N_PATCHES: int = 8
_MIN_SIDE_FRAC: float = 0.18    # fracción mínima de min(H,W) para el lado del parche
_MAX_SIDE_FRAC: float = 0.70    # fracción máxima
_SEGMENT_H_FACTOR: float = 1.60 # cuántas veces la altura del segmento vale el lado
_WIDTH_FACTOR: float = 1.45     # cuántas veces el ancho local vale el lado


class CurvePatchStage(PipelineStage):
    """
    Divide la radiografía normalizada en N parches cuadrados dinámicos
    centrados sobre cada segmento de la curva espinal refinada (DP).
    """

    name = "curve_patch"

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(
        self,
        payload: dict[str, Any],
        context: PipelineContext,
        logger: PipelineLogger,
    ) -> dict[str, Any]:

        # Saltar si el stage previo fue saltado
        if payload.get("curve_refinement_skipped", False):
            logger.warn("CurvePatchStage: CurveRefinementStage fue saltado. Stage saltado.")
            payload["curve_patch_skipped"] = True
            return payload

        if not payload.get("curve_refinement_done", False):
            logger.warn(
                "CurvePatchStage: no hay salida de CurveRefinementStage en el payload. Stage saltado."
            )
            payload["curve_patch_skipped"] = True
            return payload

        # ── 1. Leer entradas ──────────────────────────────────────────
        image: np.ndarray = payload["image"]
        binary_mask: np.ndarray = payload["binary_mask"]
        dp_ys: np.ndarray = np.asarray(payload["dp_ys"], dtype=np.float32)
        dp_xs: np.ndarray = np.asarray(payload["dp_xs"], dtype=np.float32)
        dp_mask: np.ndarray = payload.get("dp_mask", None)

        # Imagen a float [0,1] escala de grises
        if image.ndim == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        img01 = self._norm01(image)
        H, W = img01.shape

        # Máscara binaria uint8 {0,1}
        binary = (binary_mask > 0).astype(np.uint8)
        if binary.shape != (H, W):
            binary = cv2.resize(binary, (W, H), interpolation=cv2.INTER_NEAREST)

        # Máscara curva uint8 {0,1}
        if dp_mask is not None:
            curve_m = (dp_mask > 0).astype(np.uint8)
            if curve_m.shape != (H, W):
                curve_m = cv2.resize(curve_m, (W, H), interpolation=cv2.INTER_NEAREST)
        else:
            curve_m = self._draw_curve_mask(dp_ys, dp_xs, H, W)

        # Número de parches (configurable vía metadata o constante por defecto)
        n_patches: int = int(context.metadata.get("n_curve_patches", _N_PATCHES))

        if len(dp_ys) < n_patches:
            logger.warn(
                f"CurvePatchStage: curva tiene {len(dp_ys)} puntos, "
                f"menos que n_curve_patches={n_patches}. Stage saltado."
            )
            payload["curve_patch_skipped"] = True
            return payload

        # Curva como array [[y, x], ...]
        curve = np.stack([dp_ys, dp_xs], axis=1)  # [N_pts, 2]

        # ── 2. Directorios de salida ──────────────────────────────────
        out_root = context.outputs_dir / "curve_patches"
        img_dir  = out_root / "images"
        bin_dir  = out_root / "binary"
        crv_dir  = out_root / "curve"
        for d in (img_dir, bin_dir, crv_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Clave del paciente (para nombrar los archivos)
        patient_key = str(context.metadata.get("request_id", "patient"))

        # ── 3. Segmentación y crop ────────────────────────────────────
        idx_edges = np.linspace(0, len(curve) - 1, n_patches + 1).astype(int)

        patch_rows: list[dict] = []
        patches_out: list[np.ndarray] = []

        for patch_idx in range(n_patches):
            a = idx_edges[patch_idx]
            b = idx_edges[patch_idx + 1]

            if b <= a:
                logger.warn(f"CurvePatchStage: segmento {patch_idx} vacío (a={a}, b={b}). Saltando.")
                continue

            seg = curve[a : b + 1]

            cy = float(np.median(seg[:, 0]))
            cx = float(np.median(seg[:, 1]))

            seg_h = float(seg[:, 0].max() - seg[:, 0].min() + 1)

            local_width = self._local_binary_width(
                binary=binary,
                y1=int(seg[:, 0].min()),
                y2=int(seg[:, 0].max()),
                fallback=0.30 * W,
            )

            min_side = _MIN_SIDE_FRAC * min(H, W)
            max_side = _MAX_SIDE_FRAC * min(H, W)

            side = max(
                min_side,
                _SEGMENT_H_FACTOR * seg_h,
                _WIDTH_FACTOR * local_width,
            )
            side = min(side, max_side)

            patch_img,  meta = self._crop_square(img01,                     cy, cx, side)
            patch_bin,  _    = self._crop_square(binary.astype(np.float32), cy, cx, side)
            patch_crv,  _    = self._crop_square(curve_m.astype(np.float32), cy, cx, side)

            # ── 4. Guardar PNGs ───────────────────────────────────────
            base = f"{patient_key}__patch{patch_idx:02d}"

            img_path  = img_dir / f"{base}.png"
            bin_path  = bin_dir / f"{base}_binary.png"
            crv_path  = crv_dir / f"{base}_curve.png"

            cv2.imwrite(str(img_path),  (np.clip(patch_img, 0, 1) * 255).astype(np.uint8))
            cv2.imwrite(str(bin_path),  (np.clip(patch_bin, 0, 1) * 255).astype(np.uint8))
            cv2.imwrite(str(crv_path),  (np.clip(patch_crv, 0, 1) * 255).astype(np.uint8))

            patches_out.append(patch_img)

            patch_rows.append(
                {
                    "patient_key":        patient_key,
                    "patch_idx":          patch_idx,
                    "source_h":           int(H),
                    "source_w":           int(W),
                    "center_y_full":      round(cy, 2),
                    "center_x_full":      round(cx, 2),
                    "segment_start_idx":  int(a),
                    "segment_end_idx":    int(b),
                    "segment_h_full":     round(seg_h, 2),
                    "local_width_full":   round(local_width, 2),
                    "side":               round(float(side), 2),
                    "patch_image_path":   str(img_path),
                    "patch_binary_path":  str(bin_path),
                    "patch_curve_path":   str(crv_path),
                    **meta,
                }
            )

        if not patch_rows:
            logger.warn("CurvePatchStage: no se generó ningún parche. Stage saltado.")
            payload["curve_patch_skipped"] = True
            return payload

        # ── 5. Guardar CSV ────────────────────────────────────────────
        import pandas as pd  # lazy import — no necesario en todo el módulo

        csv_path = out_root / "curve_patch_manifest.csv"
        pd.DataFrame(patch_rows).to_csv(csv_path, index=False)

        logger.info(
            f"CurvePatchStage: {len(patch_rows)} parches guardados en {out_root}"
        )

        # ── 6. Visualización ──────────────────────────────────────────
        if context.metadata.get("plots_show", False):
            self._show_patch_debug(patches_out, patch_rows, img01, curve, binary, curve_m)

        # ── 7. Actualizar payload ─────────────────────────────────────
        payload["patch_dir"]        = str(out_root)
        payload["patch_csv_path"]   = str(csv_path)
        payload["patch_count"]      = len(patch_rows)
        payload["patches"]          = patches_out
        payload["patch_meta"]       = patch_rows
        payload["curve_patch_done"] = True

        return payload

    # ------------------------------------------------------------------
    # Helpers privados — algoritmo
    # ------------------------------------------------------------------

    @staticmethod
    def _norm01(arr: np.ndarray) -> np.ndarray:
        arr = arr.astype(np.float32)
        mn, mx = float(arr.min()), float(arr.max())
        if mx - mn < 1e-8:
            return np.zeros_like(arr)
        return (arr - mn) / (mx - mn)

    @staticmethod
    def _draw_curve_mask(
        ys: np.ndarray,
        xs: np.ndarray,
        H: int,
        W: int,
    ) -> np.ndarray:
        """Dibuja la curva DP como máscara binaria mediante cv2.polylines."""
        m = np.zeros((H, W), dtype=np.uint8)
        pts = np.stack(
            [np.clip(np.round(xs).astype(int), 0, W - 1),
             np.clip(np.round(ys).astype(int), 0, H - 1)],
            axis=1,
        ).astype(np.int32)
        if len(pts) >= 2:
            thickness = max(2, int(round(min(H, W) * 0.006)))
            cv2.polylines(m, [pts], isClosed=False, color=1, thickness=thickness)
        return m

    @staticmethod
    def _local_binary_width(
        binary: np.ndarray,
        y1: int,
        y2: int,
        fallback: float,
    ) -> float:
        """Estima el ancho mediano de la máscara binaria en el rango de filas [y1, y2]."""
        H = binary.shape[0]
        y1 = int(np.clip(y1, 0, H - 1))
        y2 = int(np.clip(y2, 0, H - 1))
        if y2 <= y1:
            return fallback
        widths = []
        for y in range(y1, y2 + 1):
            cols = np.where(binary[y] > 0)[0]
            if len(cols) > 3:
                widths.append(float(cols.max() - cols.min() + 1))
        return float(np.median(widths)) if widths else fallback

    @staticmethod
    def _crop_square(
        img: np.ndarray,
        cy: float,
        cx: float,
        side: float,
    ) -> tuple[np.ndarray, dict]:
        """
        Recorta un cuadrado de 'side' píxeles centrado en (cy, cx).
        Aplica padding con ceros si el recorte sale fuera de los bordes.
        Devuelve (patch, meta_dict).
        """
        H, W = img.shape[:2]
        side = int(round(max(8.0, side)))
        half = side // 2

        y1 = int(round(cy)) - half
        x1 = int(round(cx)) - half
        y2 = y1 + side
        x2 = x1 + side

        pt = int(max(0, -y1))
        pl = int(max(0, -x1))
        pb = int(max(0, y2 - H))
        pr = int(max(0, x2 - W))

        img_pad = np.pad(img, ((pt, pb), (pl, pr)), mode="constant", constant_values=0)

        y1p = y1 + pt
        y2p = y2 + pt
        x1p = x1 + pl
        x2p = x2 + pl

        patch = img_pad[y1p:y2p, x1p:x2p].copy()

        meta = {
            "crop_y1":     int(y1),
            "crop_y2":     int(y2),
            "crop_x1":     int(x1),
            "crop_x2":     int(x2),
            "crop_side":   side,
            "pad_top":     pt,
            "pad_bottom":  pb,
            "pad_left":    pl,
            "pad_right":   pr,
        }
        return patch.astype(np.float32), meta

    # ------------------------------------------------------------------
    # Visualización — debug espacial
    # ------------------------------------------------------------------

    def _show_patch_debug(
        self,
        patches: list[np.ndarray],
        meta: list[dict],
        img01: np.ndarray,
        curve: np.ndarray,
        binary: np.ndarray,
        curve_m: np.ndarray,
    ) -> None:
        """
        Figura de debug en dos filas:

        Fila 0 — OVERVIEW ESPACIAL (panel único ancho):
            Imagen normalizada completa + curva DP (polyline rojo) +
            cajas de todos los parches (rectángulos coloreados numerados).
            Permite ver de un vistazo dónde quedan los parches sobre la RX.

        Fila 1 — N paneles individuales:
            Cada parche con overlay de la curva DP (rojo semitransparente).
            El borde del panel tiene el mismo color que la caja del overview.
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.colors import hsv_to_rgb

        n = len(patches)
        if n == 0:
            return

        # Paleta de colores: uno por parche, matiz distribuido uniformemente
        colors = [
            hsv_to_rgb([(i / max(n, 1)) * 0.82, 0.90, 0.95])
            for i in range(n)
        ]

        fig = plt.figure(figsize=(max(14, 2.2 * n), 11))

        # ── Fila 0: overview espacial ─────────────────────────────────
        ax_top = fig.add_subplot(2, 1, 1)
        ax_top.imshow(img01, cmap="gray", vmin=0, vmax=1)

        # Curva DP como polyline
        if len(curve) >= 2:
            ax_top.plot(
                curve[:, 1], curve[:, 0],
                color="red", linewidth=1.5, alpha=0.80, label="curva DP",
            )

        # Caja de cada parche
        for i, row in enumerate(meta):
            # crop_y1/x1 pueden salir fuera de la imagen (padding externo);
            # dibujamos con las coordenadas originales del espacio imagen.
            y1_draw = max(row["crop_y1"], 0)
            x1_draw = max(row["crop_x1"], 0)
            side_draw = row["crop_side"]

            rect = mpatches.Rectangle(
                (x1_draw, y1_draw),
                side_draw, side_draw,
                linewidth=1.8,
                edgecolor=colors[i],
                facecolor="none",
                alpha=0.90,
            )
            ax_top.add_patch(rect)

            # Número del parche centrado dentro de la caja
            ax_top.text(
                x1_draw + side_draw * 0.5,
                y1_draw + side_draw * 0.5,
                str(i),
                color=colors[i],
                fontsize=9,
                fontweight="bold",
                ha="center",
                va="center",
            )

            # Centroide marcado con cruz pequeña
            ax_top.plot(
                row["center_x_full"], row["center_y_full"],
                marker="+", markersize=6, color=colors[i], markeredgewidth=1.2,
            )

        ax_top.set_title(
            "Overview espacial — curva DP (rojo) + parches (cajas coloreadas) sobre imagen normalizada",
            fontsize=9,
        )
        ax_top.axis("off")

        # ── Fila 1: parches individuales ──────────────────────────────
        for i, (patch, row) in enumerate(zip(patches, meta)):
            cy   = row["center_y_full"]
            cx   = row["center_x_full"]
            side = row["crop_side"]

            patch_crv, _ = self._crop_square(
                curve_m.astype(np.float32), cy, cx, side
            )

            ax = fig.add_subplot(2, n, n + i + 1)
            ax.imshow(patch, cmap="gray", vmin=0, vmax=1)
            ax.imshow(patch_crv, cmap="Reds", alpha=0.50, vmin=0, vmax=1)

            ax.set_title(f"p{i:02d}\n{side}px", fontsize=7)
            ax.axis("off")

            # Borde del panel con el mismo color que la caja del overview
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_edgecolor(colors[i])
                spine.set_linewidth(2.5)

        fig.suptitle(
            f"CurvePatchStage — {n} parches alineados a la curva espinal [debug]",
            fontsize=10,
            y=1.01,
        )
        plt.tight_layout()
        plt.show()
