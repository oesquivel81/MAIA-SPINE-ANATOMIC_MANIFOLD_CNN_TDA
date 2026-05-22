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

        # ---------------------------------------------------------------
        # 1. Validar binary_mask y ajustar tamaño
        # ---------------------------------------------------------------
        if binary_mask is None:
            logger.warn(
                "!!! CurveRefinementStage: binary_mask NO encontrada en payload. Stage saltado."
            )
            payload["curve_refinement_skipped"] = True
            return payload

        if binary_mask.shape != (H, W):
            binary_mask = cv2.resize(
                binary_mask.astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST
            )

        bm_max = float(binary_mask.max())
        logger.debug(
            f"CurveRefinementStage: img={img01.shape}, "
            f"binary_mask max={bm_max:.3f}, coverage (>0)={(binary_mask > 0).mean() * 100:.1f}%"
        )

        # ---------------------------------------------------------------
        # 2. Binarizar con threshold adaptable + morfología + componente mayor
        #    Si el mapa es float [0,1] → threshold 0.35
        #    Si es uint8 [0,255] → threshold 0.35 * 255
        # ---------------------------------------------------------------
        bm_thr = 0.35 if bm_max <= 1.0 else (0.35 * 255.0)
        mask_bin = (binary_mask >= bm_thr).astype(np.uint8)
        logger.debug(
            f"CurveRefinementStage: threshold={bm_thr:.1f} → coverage={mask_bin.mean() * 100:.1f}%"
        )

        _kernel5 = np.ones((5, 5), np.uint8)
        mask_bin = cv2.morphologyEx(mask_bin, cv2.MORPH_CLOSE, _kernel5)
        mask_bin = cv2.morphologyEx(mask_bin, cv2.MORPH_OPEN,  _kernel5)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_bin, connectivity=8)
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            largest_label = 1 + int(np.argmax(areas))
            mask_bin = (labels == largest_label).astype(np.uint8)
            logger.debug(
                f"CurveRefinementStage: componente mayor seleccionado "
                f"(área={areas[largest_label - 1]:.0f} px, de {num_labels - 1} componentes)"
            )

        binary_refined = mask_bin.copy()
        logger.debug(
            f"CurveRefinementStage: binary_clean coverage={binary_refined.mean() * 100:.1f}%"
        )

        # Si la máscara limpia queda vacía, caer en threshold permisivo > 0
        if binary_refined.sum() < 50:
            logger.warn(
                f"CurveRefinementStage: máscara limpia muy pequeña ({int(binary_refined.sum())} px). "
                "Usando binary_mask > 0 como fallback para binary_refined."
            )
            binary_refined = (binary_mask > 0).astype(np.uint8)
            if binary_refined.shape != (H, W):
                binary_refined = cv2.resize(binary_refined, (W, H), interpolation=cv2.INTER_NEAREST)

        # ---------------------------------------------------------------
        # 3. Skeleton — sólo como auxiliar / prior opcional para DP
        #    Nunca es la ruta principal; se ignora si cubre < 30 % de altura
        # ---------------------------------------------------------------
        skel = np.zeros((H, W), dtype=np.uint8)
        skeleton_prior_ys: np.ndarray | None = None
        skeleton_prior_xs: np.ndarray | None = None

        if binary_refined.sum() >= 50:
            try:
                from skimage.morphology import skeletonize as _skeletonize
                skel = _skeletonize(binary_refined > 0).astype(np.uint8)

                _skel_ys: list[int]   = []
                _skel_xs: list[float] = []
                for _y in range(H):
                    _xx = np.where(skel[_y] > 0)[0]
                    if len(_xx) >= 1:
                        _skel_ys.append(_y)
                        _skel_xs.append(float(np.median(_xx)))

                skel_height_coverage = len(_skel_ys) / H if H > 0 else 0.0
                if len(_skel_ys) >= 20 and skel_height_coverage >= 0.30:
                    _ys_s = np.asarray(_skel_ys, dtype=np.float32)
                    _xs_s = np.asarray(_skel_xs, dtype=np.float32)
                    _yf   = np.arange(int(_ys_s.min()), int(_ys_s.max()) + 1, dtype=np.float32)
                    _xf   = np.interp(_yf, _ys_s, _xs_s)
                    _xf   = gaussian_filter1d(_xf, sigma=4)
                    _xf   = np.clip(_xf, 0, W - 1)
                    skeleton_prior_ys = _yf.astype(np.int32)
                    skeleton_prior_xs = _xf.astype(np.float32)
                    logger.debug(
                        f"CurveRefinementStage: skeleton prior válido "
                        f"({len(_skel_ys)} filas, {skel_height_coverage * 100:.1f}% height)"
                    )
                else:
                    logger.debug(
                        f"CurveRefinementStage: skeleton insuficiente "
                        f"({len(_skel_ys)} filas, {skel_height_coverage * 100:.1f}% height) "
                        "→ ignorado, DP usará mediana"
                    )
            except Exception as _e:
                logger.warn(f"CurveRefinementStage: skeleton falló ({_e}) → ignorado")

        # ---------------------------------------------------------------
        # 4. Likelihood anatómico (ruta principal DP — igual que antes)
        #    likelihood = 0.62·(CLAHE+Scharr) + 0.18·banda_binaria + 0.20·bonus_curva
        # ---------------------------------------------------------------
        curve_prob = self._normalize01(curve_mask.astype(np.float32))
        if curve_prob.shape != (H, W):
            curve_prob = cv2.resize(curve_prob, (W, H), interpolation=cv2.INTER_LINEAR)

        image_likelihood, _img_clahe, _grad = self._make_image_likelihood(img01)
        curve_bonus = gaussian_filter(self._normalize01(curve_prob), sigma=2.0)

        _kernel_dil = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (45, 45))
        binary_band = cv2.dilate(binary_refined, _kernel_dil, iterations=1)
        binary_band = self._normalize01(binary_band.astype(np.float32))

        likelihood_final = (
            0.62 * image_likelihood
            + 0.18 * binary_band
            + 0.20 * curve_bonus
        )
        likelihood_final = gaussian_filter(likelihood_final, sigma=1.2)
        likelihood_final = self._normalize01(likelihood_final)

        # ---------------------------------------------------------------
        # 5. Prior curve: skeleton si disponible, si no mediana de binary_refined
        # ---------------------------------------------------------------
        curve_source: str = "dp"
        prior_ys: np.ndarray | None = None
        prior_xs: np.ndarray | None = None

        if skeleton_prior_ys is not None:
            prior_ys    = skeleton_prior_ys
            prior_xs    = skeleton_prior_xs
            curve_source = "dp_guided_by_skeleton"
            logger.debug("CurveRefinementStage: usando skeleton como prior para DP")
        else:
            prior_ys, prior_xs = self._centerline_from_mask(
                binary_refined, min_pixels_per_row=3, smooth_sigma=10
            )

        if prior_ys is None:
            # Intentar con máscara laxa como último recurso para el prior
            _binary_loose = (binary_mask > 0).astype(np.uint8)
            if _binary_loose.shape != (H, W):
                _binary_loose = cv2.resize(_binary_loose, (W, H), interpolation=cv2.INTER_NEAREST)
            prior_ys, prior_xs = self._centerline_from_mask(
                _binary_loose, min_pixels_per_row=1, smooth_sigma=10
            )

        if prior_ys is None:
            logger.warn(
                "!!! CurveRefinementStage: no se pudo construir prior desde binary. Stage saltado."
            )
            payload["curve_refinement_skipped"] = True
            return payload

        # ---------------------------------------------------------------
        # 6. Dynamic Programming — ruta principal
        # ---------------------------------------------------------------
        dp_ys: np.ndarray | None = None
        dp_xs: np.ndarray | None = None

        try:
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
            logger.debug(
                f"CurveRefinementStage: DP completado, {len(dp_ys)} puntos, source={curve_source}"
            )
        except Exception as _e:
            logger.warn(f"CurveRefinementStage: DP falló ({_e})")

        # ---------------------------------------------------------------
        # 7. Fallback chain: skeleton → mediana → error explícito
        # ---------------------------------------------------------------
        if dp_ys is None:
            if skeleton_prior_ys is not None:
                dp_ys        = skeleton_prior_ys
                dp_xs        = skeleton_prior_xs
                curve_source = "skeleton_fallback"
                logger.warn("CurveRefinementStage: DP falló → usando skeleton como fallback")
            elif prior_ys is not None:
                dp_ys        = prior_ys
                dp_xs        = prior_xs
                curve_source = "median_fallback"
                logger.warn(
                    "CurveRefinementStage: DP y skeleton fallaron → usando mediana como fallback"
                )
            else:
                logger.warn(
                    "!!! CurveRefinementStage: todos los métodos fallaron. Stage saltado."
                )
                payload["curve_refinement_skipped"] = True
                return payload

        # ---------------------------------------------------------------
        # 8. Heatmap y máscara
        # ---------------------------------------------------------------
        dp_heatmap = self._draw_curve_heatmap(img01.shape, dp_ys, dp_xs, thickness=6, blur_sigma=4)
        dp_mask    = (dp_heatmap > _HEATMAP_THRESHOLD).astype(np.uint8)

        # ---------------------------------------------------------------
        # 9. Guardar outputs
        # ---------------------------------------------------------------
        out_dir = context.outputs_dir / "curve_refinement"
        out_dir.mkdir(parents=True, exist_ok=True)

        norm_path = out_dir / "00_normalized_image.png"
        cv2.imwrite(str(norm_path), (img01 * 255).clip(0, 255).astype(np.uint8))

        # binary_mask_runtime.png — máscara original del payload (sin limpiar)
        _bm_save = binary_mask.astype(np.float32)
        if bm_max > 1.0:
            _bm_save = _bm_save / 255.0
        cv2.imwrite(
            str(out_dir / "binary_mask_runtime.png"),
            (_bm_save * 255).clip(0, 255).astype(np.uint8),
        )

        # binary_mask_clean_runtime.png — después de threshold + morfología
        cv2.imwrite(str(out_dir / "binary_mask_clean_runtime.png"), binary_refined * 255)

        # binary_skeleton_runtime.png — skeleton (vacío si no disponible)
        cv2.imwrite(str(out_dir / "binary_skeleton_runtime.png"), skel * 255)

        self._save_png(binary_refined.astype(np.float32), out_dir / "08_binary_refined.png")
        self._save_png(image_likelihood,                  out_dir / "01_image_likelihood.png")
        self._save_png(binary_band,                       out_dir / "02_binary_band.png")
        self._save_png(curve_bonus,                       out_dir / "03_curve_bonus.png")
        self._save_png(likelihood_final,                  out_dir / "04_likelihood_final.png")

        _prior_heatmap = self._draw_curve_heatmap(img01.shape, prior_ys, prior_xs, thickness=5, blur_sigma=4)
        self._save_png(_prior_heatmap,             out_dir / "05_prior_curve.png")
        self._save_png(dp_heatmap,                 out_dir / "06_curve_dp_heatmap.png")
        self._save_png(dp_mask.astype(np.float32), out_dir / "07_curve_dp_mask.png")

        np.save(out_dir / "curve_dp_heatmap.npy", dp_heatmap)
        np.save(out_dir / "curve_dp_mask.npy",    dp_mask)

        overlay_path = out_dir / "refined_curve_overlay_runtime.png"
        self._save_curve_overlay(img01, dp_ys, dp_xs, overlay_path)

        combined_path = out_dir / "combined_masks_overlay_runtime.png"
        self._save_combined_overlay(img01, binary_refined, dp_ys, dp_xs, combined_path)

        binary_curve_overlay_path: Path | None = None
        if skel.sum() > 0 and skeleton_prior_ys is not None:
            binary_curve_overlay_path = out_dir / "binary_curve_overlay_runtime.png"
            self._save_skeleton_curve_overlay(
                img01, binary_refined, skel, dp_ys, dp_xs, binary_curve_overlay_path
            )

        # refined_curve_source.txt — fuente de la curva final
        (out_dir / "refined_curve_source.txt").write_text(curve_source)

        logger.info(f"CurveRefinementStage: overlays guardados → {out_dir}")

        import pandas as pd  # lazy import
        df = pd.DataFrame({"y": dp_ys.astype(int), "x": dp_xs.astype(float)})
        csv_path = out_dir / "curve_dp_centerline.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"CurveRefinementStage: curva guardada ({curve_source}) → {csv_path}")

        metadata = {
            "strategy": curve_source,
            "request_id": context.request_id,
            "curve_source": curve_source,
            "skeleton_prior_used": skeleton_prior_ys is not None,
            "skeleton_pixels": int(skel.sum()),
            "hyperparams": {
                "search_radius":    _DP_SEARCH_RADIUS,
                "smooth_lambda":    _DP_SMOOTH_LAMBDA,
                "prior_lambda":     _DP_PRIOR_LAMBDA,
                "binary_lambda":    _DP_BINARY_LAMBDA,
                "center_lambda":    _DP_CENTER_LAMBDA,
                "heatmap_threshold": _HEATMAP_THRESHOLD,
                "bm_threshold":     bm_thr,
            },
            "curve_points":        int(len(df)),
            "curve_mask_coverage": float(dp_mask.mean()),
            "output_dir":          str(out_dir),
        }
        meta_path = out_dir / "curve_refinement_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Visualización opcional
        if context.metadata.get("plots_show", False):
            self._show_refinement_grid(
                img01, binary_refined, image_likelihood, binary_band,
                curve_bonus, likelihood_final, prior_ys, prior_xs,
                dp_ys, dp_xs, dp_heatmap, dp_mask,
            )
            self._show_curve_heatmap(
                img01, prior_ys, prior_xs, dp_ys, dp_xs, dp_heatmap, dp_mask
            )
            self._show_curve_csv(str(csv_path), dp_ys, dp_xs)

        # ---------------------------------------------------------------
        # 10. Actualizar payload
        # ---------------------------------------------------------------
        payload["dp_ys"]                 = dp_ys
        payload["dp_xs"]                 = dp_xs
        payload["dp_heatmap"]            = dp_heatmap
        payload["dp_mask"]               = dp_mask
        payload["curve_csv_path"]        = str(csv_path)
        payload["curve_meta_path"]       = str(meta_path)
        payload["curve_refinement_done"] = True
        payload["dp_curve"]              = {"dp_ys": dp_ys.tolist(), "dp_xs": dp_xs.tolist()}

        debug_images: dict = payload.get("debug_images", {})
        debug_images["normalized_image"]       = str(norm_path)
        debug_images["binary_mask_raw"]        = str(out_dir / "binary_mask_runtime.png")
        debug_images["binary_refined"]         = str(out_dir / "08_binary_refined.png")
        debug_images["binary_mask_clean"]      = str(out_dir / "binary_mask_clean_runtime.png")
        debug_images["binary_skeleton"]        = str(out_dir / "binary_skeleton_runtime.png")
        debug_images["refined_curve_overlay"]  = str(overlay_path)
        debug_images["combined_masks_overlay"] = str(combined_path)
        if binary_curve_overlay_path is not None:
            debug_images["binary_curve_overlay"] = str(binary_curve_overlay_path)
        payload["debug_images"] = debug_images

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
    def _save_curve_overlay(
        image: np.ndarray,
        dp_ys: np.ndarray,
        dp_xs: np.ndarray,
        path: Path,
        color: tuple = (0, 255, 0),
        thickness: int = 2,
    ) -> None:
        """Guarda la imagen (float [0,1] o uint8) con la curva DP superpuesta en color."""
        img8 = image.copy()
        # Normalizar a uint8 correctamente segun rango
        if img8.dtype != np.uint8:
            if img8.max() <= 1.0:
                img8 = (img8 * 255).clip(0, 255).astype(np.uint8)
            else:
                img8 = np.clip(img8, 0, 255).astype(np.uint8)
        if img8.ndim == 2:
            overlay = cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)
        else:
            overlay = img8.copy()
        pts = np.stack([dp_xs.astype(np.int32), dp_ys.astype(np.int32)], axis=1)
        cv2.polylines(overlay, [pts], isClosed=False, color=color, thickness=thickness)
        cv2.imwrite(str(path), overlay)

    @staticmethod
    def _save_combined_overlay(
        image: np.ndarray,
        binary_refined: np.ndarray,
        dp_ys: np.ndarray,
        dp_xs: np.ndarray,
        path: Path,
    ) -> None:
        """Overlay: imagen normalizada + máscara binaria refinada (azul semitransparente) + curva DP (verde)."""
        img8 = image.copy()
        if img8.dtype != np.uint8:
            if img8.max() <= 1.0:
                img8 = (img8 * 255).clip(0, 255).astype(np.uint8)
            else:
                img8 = np.clip(img8, 0, 255).astype(np.uint8)
        canvas = cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)
        # Máscara binaria refinada en azul semitransparente
        blue_layer = canvas.copy()
        blue_layer[binary_refined > 0] = [180, 60, 0]  # BGR → azul
        canvas = cv2.addWeighted(canvas, 0.65, blue_layer, 0.35, 0)
        # Curva DP en verde encima
        pts = np.stack([dp_xs.astype(np.int32), dp_ys.astype(np.int32)], axis=1)
        cv2.polylines(canvas, [pts], isClosed=False, color=(0, 255, 0), thickness=2)
        cv2.imwrite(str(path), canvas)

    @staticmethod
    def _save_skeleton_curve_overlay(
        image: np.ndarray,
        binary_clean: np.ndarray,
        skel: np.ndarray,
        dp_ys: np.ndarray,
        dp_xs: np.ndarray,
        path: Path,
    ) -> None:
        """Overlay: imagen gris + máscara limpia (azul) + skeleton (amarillo) + curva suave (verde)."""
        img8 = image.copy()
        if img8.dtype != np.uint8:
            if img8.max() <= 1.0:
                img8 = (img8 * 255).clip(0, 255).astype(np.uint8)
            else:
                img8 = np.clip(img8, 0, 255).astype(np.uint8)
        canvas = cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)
        # Máscara limpia en azul semitransparente
        blue_layer = canvas.copy()
        blue_layer[binary_clean > 0] = [180, 60, 0]
        canvas = cv2.addWeighted(canvas, 0.70, blue_layer, 0.30, 0)
        # Skeleton en amarillo
        canvas[skel > 0] = [0, 220, 220]
        # Curva suavizada en verde encima
        pts = np.stack([dp_xs.astype(np.int32), dp_ys.astype(np.int32)], axis=1)
        cv2.polylines(canvas, [pts], isClosed=False, color=(0, 255, 0), thickness=2)
        cv2.imwrite(str(path), canvas)

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

    @staticmethod
    def _show_curve_heatmap(
        img01: np.ndarray,
        prior_ys: np.ndarray,
        prior_xs: np.ndarray,
        dp_ys: np.ndarray,
        dp_xs: np.ndarray,
        dp_heatmap: np.ndarray,
        dp_mask: np.ndarray,
    ) -> None:
        """Grid 2×3 detallado de la curva DP y su heatmap."""
        import matplotlib.pyplot as plt  # lazy import

        fig, axes = plt.subplots(2, 3, figsize=(18, 12))

        # ---- Fila 0: heatmap y máscara ----
        axes[0, 0].imshow(dp_heatmap, cmap="hot")
        axes[0, 0].set_title(
            f"Heatmap DP\nmin={dp_heatmap.min():.3f}  max={dp_heatmap.max():.3f}",
            fontsize=9,
        )
        axes[0, 0].axis("off")

        axes[0, 1].imshow(dp_mask, cmap="gray")
        axes[0, 1].set_title(
            f"Máscara DP (thr={_HEATMAP_THRESHOLD})\ncoverage={dp_mask.mean() * 100:.2f}%",
            fontsize=9,
        )
        axes[0, 1].axis("off")

        axes[0, 2].imshow(img01, cmap="gray")
        axes[0, 2].imshow(dp_heatmap, cmap="hot", alpha=0.6)
        axes[0, 2].set_title("Imagen + heatmap DP", fontsize=9)
        axes[0, 2].axis("off")

        # ---- Fila 1: curvas sobre imagen ----
        axes[1, 0].imshow(img01, cmap="gray")
        axes[1, 0].plot(prior_xs, prior_ys, color="cyan", linewidth=1.5)
        axes[1, 0].set_title(f"Curva previa (centerline)\n{len(prior_ys)} pts", fontsize=9)
        axes[1, 0].axis("off")

        axes[1, 1].imshow(img01, cmap="gray")
        axes[1, 1].plot(dp_xs, dp_ys, color="lime", linewidth=2)
        axes[1, 1].set_title(f"Curva refinada DP\n{len(dp_ys)} pts", fontsize=9)
        axes[1, 1].axis("off")

        axes[1, 2].imshow(img01, cmap="gray")
        axes[1, 2].imshow(dp_heatmap, cmap="hot", alpha=0.45)
        axes[1, 2].plot(prior_xs, prior_ys, color="cyan", linewidth=1.5, label="previa")
        axes[1, 2].plot(dp_xs, dp_ys, color="lime", linewidth=2, label="DP")
        axes[1, 2].legend(loc="upper right", fontsize=7)
        axes[1, 2].set_title("Overlay completo\n(imagen + heatmap + curvas)", fontsize=9)
        axes[1, 2].axis("off")

        fig.suptitle("CurveRefinementStage — Curva DP y heatmap", fontsize=12)
        plt.tight_layout()
        plt.show()

    @staticmethod
    def _show_curve_csv(
        csv_path: str,
        dp_ys: np.ndarray,
        dp_xs: np.ndarray,
    ) -> None:
        """Muestra el contenido del CSV de la curva DP en modo debug.

        Panel izquierdo: scatter de la curva completa (x vs y).
        Panel derecho:   tabla matplotlib con head(8) + … + tail(8).
        Ademas imprime describe() y head/tail completo en stdout.
        """
        import matplotlib.pyplot as plt  # lazy import
        import pandas as pd              # lazy import

        df = pd.read_csv(csv_path)
        n = len(df)

        # --- Print en stdout (siempre visible en Colab) ---
        sep = "=" * 60
        print(f"\n{sep}")
        print(f"  curve_dp_centerline.csv  —  {n} puntos")
        print(sep)
        print(f"  Ruta : {csv_path}")
        print(f"  Shape: {df.shape}    Columnas: {list(df.columns)}")
        print(f"\n{df.describe().to_string()}")
        print(f"\n  Primeras 10 filas:")
        print(df.head(10).to_string(index=False))
        print(f"\n  Últimas 10 filas:")
        print(df.tail(10).to_string(index=False))
        print(f"{sep}\n")

        # --- Figura matplotlib ---
        col_labels = list(df.columns)
        head_rows = [
            [str(round(v, 2)) if isinstance(v, float) else str(v) for v in row]
            for row in df.head(8)[col_labels].itertuples(index=False)
        ]
        tail_rows = [
            [str(round(v, 2)) if isinstance(v, float) else str(v) for v in row]
            for row in df.tail(8)[col_labels].itertuples(index=False)
        ]
        table_data = head_rows + [["..."] * len(col_labels)] + tail_rows

        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        # Scatter curva completa
        sc = axes[0].scatter(
            df["x"], df["y"], s=2,
            c=df["y"], cmap="viridis", alpha=0.8,
        )
        plt.colorbar(sc, ax=axes[0], label="fila (y)")
        axes[0].set_title(
            f"Scatter curva DP  ({n} pts)\n"
            f"x ∈ [{df['x'].min():.1f}, {df['x'].max():.1f}]  "
            f"y ∈ [{int(df['y'].min())}, {int(df['y'].max())}]",
            fontsize=9,
        )
        axes[0].set_xlabel("x  (columna píxel)", fontsize=8)
        axes[0].set_ylabel("y  (fila píxel)", fontsize=8)
        axes[0].invert_yaxis()
        axes[0].grid(True, alpha=0.3)

        # Tabla head + ... + tail
        axes[1].axis("off")
        tbl = axes[1].table(
            cellText=table_data,
            colLabels=col_labels,
            loc="center",
            cellLoc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        tbl.scale(1.2, 1.3)
        axes[1].set_title(
            f"CSV head(8) + … + tail(8)\n{csv_path.split('/')[-1]}",
            fontsize=9,
        )

        fig.suptitle("CurveRefinementStage — Contenido CSV curva DP", fontsize=11)
        plt.tight_layout()
        plt.show()
