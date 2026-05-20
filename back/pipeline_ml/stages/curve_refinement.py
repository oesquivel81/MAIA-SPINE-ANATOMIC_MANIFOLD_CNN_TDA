"""
CurveRefinementStage — post-procesamiento de las máscaras CNN.

Recibe del payload (producido por BinaryCurveStage):
    payload["image"]        np.ndarray [H,W]  uint8 o float32  imagen normalizada
    payload["binary_mask"]  np.ndarray [H,W]  uint8  {0,1}
    payload["curve_mask"]   np.ndarray [H,W]  uint8  {0,1}

Agrega al payload:
    payload["dp_ys"]                  np.ndarray [N]   int32    coordenadas Y de la curva
    payload["dp_xs"]                  np.ndarray [N]   float32  coordenadas X de la curva
    payload["dp_heatmap"]             np.ndarray [H,W] float32  mapa de calor de la curva
    payload["dp_mask"]                np.ndarray [H,W] uint8    {0,1}
    payload["curve_csv_path"]         str  ruta al CSV de puntos (y, x)
    payload["curve_meta_path"]        str  ruta al JSON de metadata
    payload["curve_refinement_done"]  bool True

Estrategia:
    1. Construye un mapa de likelihood anatómica:
          likelihood = 0.62·(CLAHE+Scharr) + 0.18·banda_binaria + 0.20·bonus_curva
    2. Extrae una curva inicial (línea media por fila desde la binaria).
    3. Refina la curva con programación dinámica (DP) que maximiza likelihood
       con penalización de suavidad entre filas consecutivas.
    4. Guarda PNGs intermedios, heatmap .npy, curva .csv y metadata .json.

Visualización (solo si context.metadata["plots_show"] is True):
    - _show_likelihood(): 4 paneles con los mapas intermedios
    - _show_curve():      3 paneles con curva previa, curva DP y overlay final
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter, gaussian_filter1d

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.stages.base import PipelineStage

# Hiperparámetros DP (los mismos que el cuaderno Colab v2)
_DP_SEARCH_RADIUS: int = 110
_DP_SMOOTH_LAMBDA: float = 0.22
_DP_PRIOR_LAMBDA: float = 0.010
_DP_BINARY_LAMBDA: float = 0.08
_DP_CENTER_LAMBDA: float = 0.001
_DP_MAX_STEP: int = 12
_HEATMAP_THRESHOLD: float = 0.25


class CurveRefinementStage(PipelineStage):
    """
    Stage de post-procesamiento: refinamiento de la curva espinal
    mediante programación dinámica sobre un mapa de likelihood anatómica.
    """

    name = "curve_refinement"

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(
        self,
        payload: dict[str, Any],
        context: PipelineContext,
        logger: PipelineLogger,
    ) -> dict[str, Any]:

        if payload.get("binary_curve_skipped", False):
            logger.warn("CurveRefinementStage: BinaryCurveStage fue saltado. Stage saltado.")
            payload["curve_refinement_skipped"] = True
            return payload

        if not payload.get("binary_curve_done", False):
            logger.warn(
                "CurveRefinementStage: no hay salida de BinaryCurveStage en el payload. Stage saltado."
            )
            payload["curve_refinement_skipped"] = True
            return payload

        image: np.ndarray = payload["image"]
        binary_mask: np.ndarray = payload["binary_mask"]
        curve_mask: np.ndarray = payload["curve_mask"]

        # Imagen a escala de grises float [0,1]
        if image.ndim == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        img01 = self._normalize01(image)
        H, W = img01.shape

        # Normalizar máscaras y ajustar tamaño si difiere
        binary_refined = (binary_mask > 0).astype(np.uint8)
        curve_prob = self._normalize01(curve_mask.astype(np.float32))

        if binary_refined.shape != (H, W):
            binary_refined = cv2.resize(binary_refined, (W, H), interpolation=cv2.INTER_NEAREST)
        if curve_prob.shape != (H, W):
            curve_prob = cv2.resize(curve_prob, (W, H), interpolation=cv2.INTER_LINEAR)

        logger.debug(
            f"CurveRefinementStage: img={img01.shape}, "
            f"binary_coverage={binary_refined.mean() * 100:.1f}%"
        )

        # --- 1. Mapa de likelihood anatómica ---
        image_likelihood, _img_clahe, _grad = self._make_image_likelihood(img01)

        curve_bonus = gaussian_filter(self._normalize01(curve_prob), sigma=2.0)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (45, 45))
        binary_band = cv2.dilate(binary_refined, kernel, iterations=1)
        binary_band = self._normalize01(binary_band.astype(np.float32))

        likelihood_final = (
            0.62 * image_likelihood
            + 0.18 * binary_band
            + 0.20 * curve_bonus
        )
        likelihood_final = gaussian_filter(likelihood_final, sigma=1.2)
        likelihood_final = self._normalize01(likelihood_final)

        logger.debug("CurveRefinementStage: likelihood calculado")

        # --- 2. Curva inicial desde binaria ---
        prior_ys, prior_xs = self._centerline_from_mask(
            binary_refined, min_pixels_per_row=3, smooth_sigma=10
        )

        if prior_ys is None:
            logger.warn(
                "CurveRefinementStage: no se pudo construir curva inicial desde la binaria. "
                "Stage saltado."
            )
            payload["curve_refinement_skipped"] = True
            return payload

        logger.debug(f"CurveRefinementStage: curva previa: {len(prior_ys)} puntos")

        # --- 3. Curva refinada por programación dinámica ---
        dp_ys, dp_xs = self._dynamic_programming_curve(
            likelihood=likelihood_final,
            prior_ys=prior_ys,
            prior_xs=prior_xs,
            binary_mask=binary_refined,
            search_radius=_DP_SEARCH_RADIUS,
            smooth_lambda=_DP_SMOOTH_LAMBDA,
            prior_lambda=_DP_PRIOR_LAMBDA,
            binary_lambda=_DP_BINARY_LAMBDA,
            center_lambda=_DP_CENTER_LAMBDA,
        )

        dp_heatmap = self._draw_curve_heatmap(img01.shape, dp_ys, dp_xs, thickness=6, blur_sigma=4)
        dp_mask = (dp_heatmap > _HEATMAP_THRESHOLD).astype(np.uint8)

        logger.debug(
            f"CurveRefinementStage: curva DP lista, {len(dp_ys)} puntos, "
            f"coverage={dp_mask.mean() * 100:.2f}%"
        )

        # --- 4. Guardar outputs ---
        out_dir = context.outputs_dir / "curve_refinement"
        out_dir.mkdir(parents=True, exist_ok=True)

        prior_heatmap = self._draw_curve_heatmap(
            img01.shape, prior_ys, prior_xs, thickness=5, blur_sigma=4
        )
        self._save_png(image_likelihood,  out_dir / "01_image_likelihood.png")
        self._save_png(binary_band,       out_dir / "02_binary_band.png")
        self._save_png(curve_bonus,       out_dir / "03_curve_bonus.png")
        self._save_png(likelihood_final,  out_dir / "04_likelihood_final.png")
        self._save_png(prior_heatmap,     out_dir / "05_prior_curve.png")
        self._save_png(dp_heatmap,        out_dir / "06_curve_dp_heatmap.png")
        self._save_png(dp_mask.astype(np.float32), out_dir / "07_curve_dp_mask.png")

        np.save(out_dir / "curve_dp_heatmap.npy", dp_heatmap)
        np.save(out_dir / "curve_dp_mask.npy", dp_mask)

        import pandas as pd  # lazy import — pandas no es requerido en todos los entornos
        df = pd.DataFrame({"y": dp_ys.astype(int), "x": dp_xs.astype(float)})
        csv_path = out_dir / "curve_dp_centerline.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"CurveRefinementStage: curva guardada en {csv_path}")

        metadata = {
            "strategy": "image_binary_curve_dynamic_programming_refinement",
            "request_id": context.request_id,
            "hyperparams": {
                "search_radius": _DP_SEARCH_RADIUS,
                "smooth_lambda": _DP_SMOOTH_LAMBDA,
                "prior_lambda": _DP_PRIOR_LAMBDA,
                "binary_lambda": _DP_BINARY_LAMBDA,
                "center_lambda": _DP_CENTER_LAMBDA,
                "heatmap_threshold": _HEATMAP_THRESHOLD,
            },
            "curve_points": int(len(df)),
            "curve_mask_coverage": float(dp_mask.mean()),
            "output_dir": str(out_dir),
        }
        meta_path = out_dir / "curve_refinement_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # --- 5. Visualización ---
        if context.metadata.get("plots_show", False):
            self._show_refinement_grid(
                img01, binary_refined, image_likelihood, binary_band,
                curve_bonus, likelihood_final,
                prior_ys, prior_xs, dp_ys, dp_xs, dp_heatmap, dp_mask,
            )

        # --- 6. Actualizar payload ---
        payload["dp_ys"] = dp_ys
        payload["dp_xs"] = dp_xs
        payload["dp_heatmap"] = dp_heatmap
        payload["dp_mask"] = dp_mask
        payload["curve_csv_path"] = str(csv_path)
        payload["curve_meta_path"] = str(meta_path)
        payload["curve_refinement_done"] = True

        return payload

    # ------------------------------------------------------------------
    # Helpers de procesamiento
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize01(x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float32)
        mn, mx = float(np.nanmin(x)), float(np.nanmax(x))
        if mx - mn < 1e-8:
            return np.zeros_like(x)
        return (x - mn) / (mx - mn)

    @staticmethod
    def _save_png(arr: np.ndarray, path: Path) -> None:
        arr = CurveRefinementStage._normalize01(arr)
        img = (arr * 255).clip(0, 255).astype(np.uint8)
        cv2.imwrite(str(path), img)

    @staticmethod
    def _make_image_likelihood(
        img01: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Mapa de probabilidad anatómica basado en CLAHE + gradiente Scharr."""
        img8 = (img01 * 255).astype(np.uint8)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        eq = clahe.apply(img8).astype(np.float32) / 255.0

        blur = cv2.GaussianBlur(eq, (0, 0), 1.2)
        gx = cv2.Scharr(blur, cv2.CV_32F, 1, 0)
        gy = cv2.Scharr(blur, cv2.CV_32F, 0, 1)
        grad = CurveRefinementStage._normalize01(np.sqrt(gx * gx + gy * gy))

        likelihood = gaussian_filter(
            0.65 * CurveRefinementStage._normalize01(eq) + 0.35 * grad, sigma=1.3
        )
        return (
            CurveRefinementStage._normalize01(likelihood),
            CurveRefinementStage._normalize01(eq),
            grad,
        )

    @staticmethod
    def _centerline_from_mask(
        mask: np.ndarray,
        min_pixels_per_row: int = 3,
        smooth_sigma: float = 10.0,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Centro inicial: mediana horizontal por fila sobre la máscara binaria."""
        mask = mask.astype(bool)
        h, w = mask.shape
        ys, xs = [], []

        for y in range(h):
            xx = np.where(mask[y])[0]
            if len(xx) >= min_pixels_per_row:
                ys.append(y)
                xs.append(float(np.median(xx)))

        if len(ys) < 10:
            return None, None

        ys_arr = np.asarray(ys, dtype=np.float32)
        xs_arr = np.asarray(xs, dtype=np.float32)
        y_full = np.arange(int(ys_arr.min()), int(ys_arr.max()) + 1, dtype=np.float32)
        x_full = np.interp(y_full, ys_arr, xs_arr)
        x_full = gaussian_filter1d(x_full, sigma=smooth_sigma)
        x_full = np.clip(x_full, 0, w - 1)

        return y_full.astype(np.int32), x_full.astype(np.float32)

    @staticmethod
    def _dynamic_programming_curve(
        likelihood: np.ndarray,
        prior_ys: np.ndarray,
        prior_xs: np.ndarray,
        binary_mask: np.ndarray | None = None,
        search_radius: int = 90,
        smooth_lambda: float = 0.18,
        prior_lambda: float = 0.015,
        binary_lambda: float = 0.10,
        center_lambda: float = 0.002,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Trayectoria x(y) que maximiza likelihood con suavidad entre filas.

        Implementación vectorizada: itera sobre offsets (-max_step..max_step)
        en lugar de iterar sobre columnas — ~25× más rápida que el bucle original.
        """
        h, w = likelihood.shape
        y0, y1 = int(prior_ys.min()), int(prior_ys.max())
        y_range = np.arange(y0, y1 + 1)
        prior_interp = np.interp(y_range, prior_ys, prior_xs)

        # Bonus de distancia a la máscara binaria
        if binary_mask is not None:
            dist_bin = distance_transform_edt(1 - binary_mask.astype(np.uint8))
            binary_bonus = np.exp(-dist_bin / 18.0)
        else:
            binary_bonus = np.zeros_like(likelihood)

        image_center = w / 2.0
        xx_grid = np.arange(w, dtype=np.float32)
        n = len(y_range)
        max_step = _DP_MAX_STEP

        dp   = np.full((n, w), np.inf, dtype=np.float32)
        back = np.zeros((n, w), dtype=np.int32)

        def _row_cost(i: int) -> np.ndarray:
            y   = y_range[i]
            px  = prior_interp[i]
            x_min = max(0, int(px - search_radius))
            x_max = min(w - 1, int(px + search_radius))
            prior_pen  = ((xx_grid - px) / max(1.0, search_radius)) ** 2
            center_pen = ((xx_grid - image_center) / w) ** 2
            rc = (
                -1.8 * likelihood[y]
                - binary_lambda * binary_bonus[y]
                + prior_lambda * prior_pen
                + center_lambda * center_pen
            )
            rc[:x_min]    += 5.0
            rc[x_max + 1:] += 5.0
            return rc

        dp[0] = _row_cost(0)

        for i in range(1, n):
            rc   = _row_cost(i)
            prev = dp[i - 1]
            best_val  = np.full(w, np.inf, dtype=np.float32)
            best_from = np.zeros(w, dtype=np.int32)

            for delta in range(-max_step, max_step + 1):
                x_from = np.arange(w) + delta
                valid  = (x_from >= 0) & (x_from < w)
                x_from_c = np.clip(x_from, 0, w - 1)
                val = np.where(valid, prev[x_from_c] + smooth_lambda * float(delta ** 2), np.inf)
                better = val < best_val
                best_val  = np.where(better, val, best_val)
                best_from = np.where(better, x_from_c, best_from)

            dp[i]   = rc + best_val
            back[i] = best_from

        # Backtracking
        xs_out = np.zeros(n, dtype=np.float32)
        xs_out[-1] = float(np.argmin(dp[-1]))
        for i in range(n - 2, -1, -1):
            xs_out[i] = back[i + 1, int(xs_out[i + 1])]

        xs_out = gaussian_filter1d(xs_out, sigma=5)
        xs_out = np.clip(xs_out, 0, w - 1)

        return y_range.astype(np.int32), xs_out.astype(np.float32)

    @staticmethod
    def _draw_curve_heatmap(
        shape: tuple[int, int],
        ys: np.ndarray,
        xs: np.ndarray,
        thickness: int = 6,
        blur_sigma: float = 4.0,
    ) -> np.ndarray:
        h, w = shape
        canvas = np.zeros((h, w), dtype=np.float32)
        if ys is None or xs is None or len(ys) < 2:
            return canvas

        pts = np.stack([xs, ys], axis=1).astype(np.int32)
        for i in range(len(pts) - 1):
            x1, y1 = int(pts[i, 0]),   int(pts[i, 1])
            x2, y2 = int(pts[i+1, 0]), int(pts[i+1, 1])
            cv2.line(canvas, (x1, y1), (x2, y2), 1.0, thickness)

        canvas = cv2.GaussianBlur(canvas, (0, 0), blur_sigma)
        return CurveRefinementStage._normalize01(canvas)

    # ------------------------------------------------------------------
    # Visualización (solo si plots_show=True)
    # ------------------------------------------------------------------

    @staticmethod
    def _show_refinement_grid(
        img01: np.ndarray,
        binary_refined: np.ndarray,
        image_likelihood: np.ndarray,
        binary_band: np.ndarray,
        curve_bonus: np.ndarray,
        likelihood_final: np.ndarray,
        prior_ys: np.ndarray,
        prior_xs: np.ndarray,
        dp_ys: np.ndarray,
        dp_xs: np.ndarray,
        dp_heatmap: np.ndarray,
        dp_mask: np.ndarray,
    ) -> None:
        """Grid 2×4 completo: imagen | binaria | likelihood | likelihood final
                              curva previa | curva DP | overlay | comparación."""
        import matplotlib.pyplot as plt  # lazy import

        def _stats(arr: np.ndarray) -> str:
            return (
                f"min={arr.min():.3f}  max={arr.max():.3f}\n"
                f"mean={arr.mean():.3f}  std={arr.std():.3f}"
            )

        fig, axes = plt.subplots(2, 4, figsize=(26, 12))

        # ---- Fila 0: imágenes base y likelihood ----
        axes[0, 0].imshow(img01, cmap="gray")
        axes[0, 0].set_title("Imagen normalizada", fontsize=9)
        axes[0, 0].set_xlabel(_stats(img01), fontsize=7, labelpad=4)
        axes[0, 0].axis("off")

        axes[0, 1].imshow(binary_refined, cmap="gray")
        axes[0, 1].set_title(
            f"Binaria refinada\ncoverage={binary_refined.mean() * 100:.1f}%", fontsize=9
        )
        axes[0, 1].set_xlabel(_stats(binary_refined.astype(np.float32)), fontsize=7, labelpad=4)
        axes[0, 1].axis("off")

        axes[0, 2].imshow(image_likelihood, cmap="gray")
        axes[0, 2].set_title("Likelihood imagen\n(CLAHE + Scharr)", fontsize=9)
        axes[0, 2].set_xlabel(_stats(image_likelihood), fontsize=7, labelpad=4)
        axes[0, 2].axis("off")

        axes[0, 3].imshow(likelihood_final, cmap="hot")
        axes[0, 3].set_title(
            "Likelihood final\n(0.62·img + 0.18·bin + 0.20·curva)", fontsize=9
        )
        axes[0, 3].set_xlabel(_stats(likelihood_final), fontsize=7, labelpad=4)
        axes[0, 3].axis("off")

        # ---- Fila 1: curvas ----
        axes[1, 0].imshow(img01, cmap="gray")
        axes[1, 0].plot(prior_xs, prior_ys, color="cyan", linewidth=1.5)
        axes[1, 0].set_title(f"Curva previa (centerline)\n{len(prior_ys)} pts", fontsize=9)
        axes[1, 0].axis("off")

        axes[1, 1].imshow(img01, cmap="gray")
        axes[1, 1].plot(dp_xs, dp_ys, color="lime", linewidth=2)
        axes[1, 1].set_title(f"Curva refinada DP\n{len(dp_ys)} pts", fontsize=9)
        axes[1, 1].axis("off")

        axes[1, 2].imshow(img01, cmap="gray")
        axes[1, 2].imshow(dp_heatmap, cmap="hot", alpha=0.55)
        axes[1, 2].plot(dp_xs, dp_ys, color="lime", linewidth=2)
        axes[1, 2].set_title(
            f"Overlay final\ncoverage={dp_mask.mean() * 100:.2f}%", fontsize=9
        )
        axes[1, 2].axis("off")

        axes[1, 3].imshow(img01, cmap="gray")
        axes[1, 3].plot(prior_xs, prior_ys, color="cyan", linewidth=1.5, label="previa")
        axes[1, 3].plot(dp_xs, dp_ys, color="lime", linewidth=2, label="DP")
        axes[1, 3].legend(loc="upper right", fontsize=7)
        axes[1, 3].set_title("Comparación curva previa vs DP", fontsize=9)
        axes[1, 3].axis("off")

        fig.suptitle(
            "CurveRefinementStage — Pipeline de refinamiento espinal", fontsize=12
        )
        plt.tight_layout()
        plt.show()
