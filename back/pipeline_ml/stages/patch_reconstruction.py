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
    payload["vertical_profiles"]     dict        boundary_profile, inter_profile, combined_profile (norm01 [H])
                                                 y combined_map float32 [H,W]
    payload["gap_analysis"]          dict        n_peaks, n_gap_peaks, mean_gap_spacing, std_gap_spacing,
                                                 vertebra_type, figure_path, profile_csv, peaks_csv,
                                                 df_profile (DataFrame), df_events (DataFrame)
    payload["spatial_index"]         dict        df_curve, df_centroids, df_peaks, df_match,
                                                 panel_path, n_centroids, n_peaks_proj, n_matches
    payload["recon_csv_path"]        str         ruta al CSV de métricas por cabeza
    payload["patch_reconstruction_done"] bool True

Imágenes guardadas adicionales:
    analysis_grid.png                           grid 1×4: imagen | intervertebral | boundary | señal combinada
    vertical_profiles.png                       perfiles boundary / intervertebral / merge con peaks y curvas suavizadas
    gap_peak_analysis/{pk}_gap_peak_analysis.png  figura de peaks/gaps vertebrales
    gap_peak_analysis/{pk}_gap_peak_profile.csv   perfil con scores y flags por fila
    gap_peak_analysis/{pk}_gap_peak_events.csv    tabla de peaks y gap_peaks detectados
    gap_peak_analysis/{pk}_gap_peak_summary.csv   resumen estadístico del paciente
    vertebra_gap_peak_analysis.csv              alias de events en out_root (para dataset builder)
    spatial_index/curve_spatial_index.csv       curva central con arclength y t_norm
    spatial_index/centroids_projected_to_curve.csv  centroides + proyección a curva
    spatial_index/peaks_projected_to_curve.csv      peaks gap + proyección a curva
    spatial_index/centroid_peak_spatial_index.csv   match final con spatial_order
    spatial_index/panel_spatial_index_curve_centroids_peaks.png  panel visual

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


def _norm01(v: np.ndarray) -> np.ndarray:
    """Normaliza un vector float32 al rango [0, 1]. Devuelve ceros si es constante."""
    v = np.asarray(v, dtype=np.float32)
    if len(v) == 0:
        return v
    mn, mx = float(np.nanmin(v)), float(np.nanmax(v))
    if not (np.isfinite(mn) and np.isfinite(mx)) or mx <= mn:
        return np.zeros_like(v)
    return ((v - mn) / (mx - mn + 1e-8)).astype(np.float32)


def _classify_gap_spacing(n_peaks: int, mean_spacing: float) -> str:
    """Clasifica el espaciado entre gaps vertebrales."""
    if n_peaks <= 2:
        return "few_or_weak_gaps"
    if not np.isfinite(mean_spacing):
        return "unknown"
    if mean_spacing < 12:
        return "dense_gaps"
    if mean_spacing <= 35:
        return "regular_gaps"
    return "sparse_gaps"


def _normalize01_img(x: np.ndarray) -> np.ndarray:
    """Normaliza imagen/array float o uint8 al rango [0, 1]."""
    x = np.asarray(x, dtype=np.float32)
    if x.max() > 1.5:
        x = x / 255.0
    return np.clip(x, 0.0, 1.0)


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

        # PNG (A∩B) \ vertebra: fondo blanco donde no hay soporte o señal < umbral
        # El umbral _SIGNAL_VIZ_THR = 0.06 deja en blanco los cuerpos vertebrales
        # (inter y boundary ~0 dentro del cuerpo), mostrando solo bordes y gaps.
        _SIGNAL_VIZ_THR = 0.06
        cs_p = out_root / "combined_signal.png"
        _cs_gray  = (combined_signal.clip(0.0, 1.0) * 255).astype(np.uint8)
        _viz_mask = support_map.astype(bool) & (combined_signal >= _SIGNAL_VIZ_THR)
        _cs_white = np.where(_viz_mask, _cs_gray, np.uint8(255))
        cv2.imwrite(str(cs_p), _cs_white)

        # CSV de estadísticas de la señal combinada (dentro del soporte)
        cs_csv_p = out_root / "combined_signal_stats.csv"
        _sup_bool = support_map.astype(bool)
        _sup_area_pct = round(float(_sup_bool.mean()) * 100, 4)
        _cs_csv_rows: list[dict] = []
        for _h in _HEADS:
            _vals = recon_maps[_h][_sup_bool]
            _cs_csv_rows.append({
                "source":           _h,
                "mean_in_support":  round(float(_vals.mean()), 6) if _vals.size else 0.0,
                "std_in_support":   round(float(_vals.std()),  6) if _vals.size else 0.0,
                "max_value":        round(float(_vals.max()),  6) if _vals.size else 0.0,
                "coverage_pct_0_5": round(float(np.mean(_vals >= 0.5)) * 100, 4) if _vals.size else 0.0,
                "support_area_pct": _sup_area_pct,
            })
        _cs_vals = combined_signal[_sup_bool]
        _cs_csv_rows.append({
            "source":           "combined",
            "mean_in_support":  round(float(_cs_vals.mean()), 6) if _cs_vals.size else 0.0,
            "std_in_support":   round(float(_cs_vals.std()),  6) if _cs_vals.size else 0.0,
            "max_value":        round(float(_cs_vals.max()),  6) if _cs_vals.size else 0.0,
            "coverage_pct_0_5": round(float(np.mean(_cs_vals >= 0.5)) * 100, 4) if _cs_vals.size else 0.0,
            "support_area_pct": _sup_area_pct,
        })
        _cs_fields = ["source", "mean_in_support", "std_in_support", "max_value",
                      "coverage_pct_0_5", "support_area_pct"]
        with open(cs_csv_p, "w", newline="", encoding="utf-8") as _fh:
            _cw = csv.DictWriter(_fh, fieldnames=_cs_fields)
            _cw.writeheader()
            _cw.writerows(_cs_csv_rows)

        logger.info(
            f"PatchReconstructionStage: señal combinada guardada → {cs_p}"
        )

        # ── Perfil vertical y análisis de gaps ────────────────────────
        profiles = self._profile_from_maps(
            boundary=recon_maps["boundary"],
            inter=recon_maps["intervertebral"],
            binary=recon_maps["binary"],
        )

        ag_p = out_root / "analysis_grid.png"
        self._show_analysis_grid(image, recon_maps, combined_signal, ag_p, plots_show)

        vp_p = out_root / "vertical_profiles.png"
        self._show_profiles_plot(profiles, vp_p, plots_show)

        logger.info(
            f"PatchReconstructionStage: perfiles verticales guardados → {vp_p}"
        )

        # ── Análisis de peaks/gaps ─────────────────────────────────────
        patient_key: str = context.metadata.get(
            "patient_key", context.metadata.get("patient_id", "patient")
        )
        gap_dir = out_root / "gap_peak_analysis"
        gap_dir.mkdir(parents=True, exist_ok=True)

        gap_analysis = self._analyze_peaks_gaps(
            profiles=profiles,
            patient_key=patient_key,
            out_dir=gap_dir,
            plots_show=plots_show,
        )
        logger.info(
            f"PatchReconstructionStage: gaps/peaks → {gap_analysis['figure_path']}"
        )

        # ── Índice espacial curva + centroides + peaks ─────────────────
        spatial_dir = out_root / "spatial_index"
        spatial_dir.mkdir(parents=True, exist_ok=True)
        ordered_mask: np.ndarray | None = payload.get("ordered_vertebra_mask")
        spatial_index = self._build_spatial_index(
            image=image,
            binary_map=recon_maps["binary"],
            gap_analysis=gap_analysis,
            patient_key=patient_key,
            out_dir=spatial_dir,
            plots_show=plots_show,
            ordered_mask=ordered_mask,
        )
        logger.info(
            f"PatchReconstructionStage: índice espacial → {spatial_index['panel_path']}"
        )

        # ── Visualización completa (grid 3 filas) ─────────────────────
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
        payload["combined_signal_path"] = str(cs_p)
        payload["analysis_grid_path"] = str(ag_p)
        payload["vertical_profiles"] = profiles
        payload["gap_analysis"] = gap_analysis
        payload["spatial_index"] = spatial_index
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

        El soporte es la **intersección** A∩B:
            A = binary_n > 0.30  (estructura espinal detectada)
            B = coverage_map > 0 (cubierto por al menos un parche)
        Esto evita incluir los parches cuadrados fuera de la columna
        (A∪B incluiría regiones sin señal que aparecerían como cuadros negros).

        Para la visualización PNG se aplica además un umbral mínimo de señal
        (``_SIGNAL_VIZ_THR``) que deja en blanco los cuerpos vertebrales
        (baja señal dentro del soporte): efecto (A∩B) \ vertebra.

        Returns:
            support_map:     uint8 {0,1}  — máscara de soporte (A∩B)
            combined_signal: float32      — señal ponderada dentro del soporte
                                            (puede superar 1.0 ligeramente;
                                            clipear al guardar PNG)
        """
        binary_n        = recon_maps["binary"]
        boundary_n      = recon_maps["boundary"]
        inter_n         = recon_maps["intervertebral"]
        ordinal_n       = recon_maps["ordinal"]

        # A∩B: solo píxeles con estructura espinal detectada Y cubiertos por parches
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
        plt.close(fig)

    # ------------------------------------------------------------------
    # Grid análisis: imagen · intervertebral · boundary · señal combinada
    # ------------------------------------------------------------------

    @staticmethod
    def _show_analysis_grid(
        image: np.ndarray,
        recon_maps: dict[str, np.ndarray],
        combined_signal: np.ndarray,
        out_path: Path,
        plots_show: bool = False,
    ) -> None:
        """
        Grid 1×4: imagen | intervertebral | boundary | señal combinada.
        Siempre guarda PNG en ``out_path``; muestra en pantalla solo si
        ``plots_show`` es True.
        """
        import matplotlib.pyplot as plt

        inter   = recon_maps["intervertebral"]
        bnd     = recon_maps["boundary"]
        vmax_cs = float(combined_signal.max()) or 1.0

        fig, axes = plt.subplots(1, 4, figsize=(14, 4))

        axes[0].imshow(image if image.ndim == 2 else image[:, :, 0], cmap="gray")
        axes[0].set_title("Imagen", fontsize=8, fontweight="bold")
        axes[0].axis("off")

        axes[1].imshow(inter, cmap="gray_r", vmin=0, vmax=1)
        axes[1].set_title(
            f"Intervertebral\ncov={np.mean(inter >= _THRESHOLD)*100:.1f}%",
            fontsize=7,
        )
        axes[1].axis("off")

        axes[2].imshow(bnd, cmap="gray_r", vmin=0, vmax=1)
        axes[2].set_title(
            f"Boundary\ncov={np.mean(bnd >= _THRESHOLD)*100:.1f}%",
            fontsize=7,
        )
        axes[2].axis("off")

        axes[3].imshow(combined_signal, cmap="gray_r", vmin=0, vmax=vmax_cs)
        axes[3].set_title(
            f"Señal combinada\n0.55·bnd+0.85·inter+0.15·ord\nmax={vmax_cs:.2f}",
            fontsize=7,
        )
        axes[3].axis("off")

        fig.suptitle(
            "Análisis estructural — intervertebral · boundary · señal combinada",
            fontsize=9,
        )
        plt.tight_layout()
        fig.savefig(str(out_path), dpi=120, bbox_inches="tight")
        if plots_show:
            plt.show()
        plt.close(fig)

    # ------------------------------------------------------------------
    # Perfiles verticales: gaps, peaks y curvas suavizadas
    # ------------------------------------------------------------------

    @staticmethod
    def _show_profiles_plot(
        profiles: dict[str, np.ndarray],
        out_path: Path,
        plots_show: bool = False,
    ) -> None:
        """
        Gráfica de perfiles verticales con curvas suavizadas y marcado de peaks.

        Columnas:
          0 — boundary  (raw + suavizada + peaks)
          1 — intervertebral (raw + suavizada + peaks)
          2 — merge: boundary_s · inter_s · combinada_s + peaks

        Siempre guarda PNG en ``out_path``; muestra en pantalla solo si
        ``plots_show`` es True.
        """
        import matplotlib.pyplot as plt

        # ── Suavizado ──────────────────────────────────────────────────
        try:
            from scipy.ndimage import gaussian_filter1d as _gf
            sigma   = 3
            bnd_s   = _gf(profiles["boundary_profile"],  sigma)
            inter_s = _gf(profiles["inter_profile"],     sigma)
            comb_s  = _gf(profiles["combined_profile"],  sigma)
        except ImportError:
            def _smooth(v: np.ndarray, w: int = 9) -> np.ndarray:
                k = np.exp(-0.5 * ((np.arange(w) - w // 2) / (w / 4.0)) ** 2)
                k /= k.sum()
                return np.convolve(v, k, mode="same").astype(np.float32)
            bnd_s   = _smooth(profiles["boundary_profile"])
            inter_s = _smooth(profiles["inter_profile"])
            comb_s  = _smooth(profiles["combined_profile"])

        # ── Detección de peaks ─────────────────────────────────────────
        try:
            from scipy.signal import find_peaks as _fp
            _kw = {"distance": 8, "prominence": 0.05}
            peaks_bnd,   _ = _fp(bnd_s,   **_kw)
            peaks_inter, _ = _fp(inter_s, **_kw)
            peaks_comb,  _ = _fp(comb_s,  **_kw)
        except ImportError:
            def _find_peaks(v: np.ndarray, min_dist: int = 8) -> np.ndarray:
                cands = np.where((v[1:-1] > v[:-2]) & (v[1:-1] > v[2:]))[0] + 1
                out: list[int] = []
                last = -min_dist
                for i in sorted(cands.tolist(), key=lambda x: -float(v[x])):
                    if i - last >= min_dist:
                        out.append(i)
                        last = i
                return np.array(sorted(out), dtype=np.int32)
            peaks_bnd   = _find_peaks(bnd_s)
            peaks_inter = _find_peaks(inter_s)
            peaks_comb  = _find_peaks(comb_s)

        H = len(profiles["combined_profile"])
        y = np.arange(H)

        fig, axes = plt.subplots(1, 3, figsize=(14, 5), sharey=True)

        # ── Col 0: boundary ────────────────────────────────────────────
        axes[0].plot(profiles["boundary_profile"], y,
                     color="#aaaaaa", lw=0.8, alpha=0.6, label="raw")
        axes[0].plot(bnd_s, y,
                     color="#2196F3", lw=1.8, label="suavizada")
        if len(peaks_bnd):
            axes[0].scatter(bnd_s[peaks_bnd], peaks_bnd,
                            s=45, color="#F44336", zorder=5,
                            label=f"peaks ({len(peaks_bnd)})")
        axes[0].set_title("Boundary\nperfil vertical", fontsize=8)
        axes[0].set_xlabel("Activación media", fontsize=7)
        axes[0].set_ylabel("Fila (px)", fontsize=7)
        axes[0].invert_yaxis()
        axes[0].legend(fontsize=6)
        axes[0].grid(True, alpha=0.3)

        # ── Col 1: intervertebral ──────────────────────────────────────
        axes[1].plot(profiles["inter_profile"], y,
                     color="#aaaaaa", lw=0.8, alpha=0.6, label="raw")
        axes[1].plot(inter_s, y,
                     color="#4CAF50", lw=1.8, label="suavizada")
        if len(peaks_inter):
            axes[1].scatter(inter_s[peaks_inter], peaks_inter,
                            s=45, color="#F44336", zorder=5,
                            label=f"peaks ({len(peaks_inter)})")
        axes[1].set_title("Intervertebral\nperfil vertical", fontsize=8)
        axes[1].set_xlabel("Activación media", fontsize=7)
        axes[1].invert_yaxis()
        axes[1].legend(fontsize=6)
        axes[1].grid(True, alpha=0.3)

        # ── Col 2: merge ───────────────────────────────────────────────
        axes[2].plot(profiles["combined_profile"], y,
                     color="#aaaaaa", lw=0.8, alpha=0.6, label="raw combinada")
        axes[2].plot(bnd_s,   y, color="#2196F3", lw=1.0, alpha=0.5, label="boundary_s")
        axes[2].plot(inter_s, y, color="#4CAF50", lw=1.0, alpha=0.5, label="inter_s")
        axes[2].plot(comb_s,  y, color="#FF9800", lw=2.2,             label="merge suavizada")
        if len(peaks_comb):
            axes[2].scatter(comb_s[peaks_comb], peaks_comb,
                            s=55, color="#F44336", zorder=5,
                            label=f"peaks ({len(peaks_comb)})")
        axes[2].set_title("Merge — curva combinada\ngaps y peaks vertebrales", fontsize=8)
        axes[2].set_xlabel("Activación media", fontsize=7)
        axes[2].invert_yaxis()
        axes[2].legend(fontsize=6)
        axes[2].grid(True, alpha=0.3)

        fig.suptitle("Estudio de gaps y peaks — perfiles vertebrales", fontsize=9)
        plt.tight_layout()
        fig.savefig(str(out_path), dpi=120, bbox_inches="tight")
        if plots_show:
            plt.show()
        plt.close(fig)

    # ------------------------------------------------------------------
    # Análisis cuantitativo: peaks, gaps, espaciado vertebral
    # ------------------------------------------------------------------

    @staticmethod
    def _analyze_peaks_gaps(
        profiles: dict[str, np.ndarray],
        patient_key: str,
        out_dir: Path,
        plots_show: bool = False,
        distance: int = 8,
        prominence: float = 0.05,
        smooth_sigma: float = 2.0,
    ) -> dict:
        """
        Análisis de gaps y peaks vertebrales sobre los perfiles verticales.

        Equivalente a ``analyze_patient_peaks_gaps`` del cuaderno.

        Parameters
        ----------
        profiles      : dict de ``_profile_from_maps()`` con
                        boundary_profile, inter_profile y combined_profile.
        patient_key   : identificador del paciente (nombra archivos de salida).
        out_dir       : directorio de salida; se crea si no existe.
        plots_show    : mostrar figura en pantalla además de guardarla.
        distance      : distancia mínima entre peaks (scipy.signal.find_peaks).
        prominence    : prominencia mínima para considerar un peak.
        smooth_sigma  : sigma del filtro gaussiano para suavizado.

        Returns
        -------
        dict con claves: ``n_peaks``, ``n_gap_peaks``, ``mean_gap_spacing``,
        ``std_gap_spacing``, ``vertebra_type``, ``figure_path``,
        ``profile_csv``, ``peaks_csv``, ``summary_csv``,
        ``df_profile`` (DataFrame), ``df_events`` (DataFrame).
        """
        import matplotlib.pyplot as plt
        import pandas as pd
        from scipy.ndimage import gaussian_filter1d as _gf
        from scipy.signal import find_peaks as _fp

        # ── Señales ────────────────────────────────────────────────────
        inter_raw   = _norm01(profiles["inter_profile"])
        bnd_raw     = _norm01(profiles["boundary_profile"])
        comb_raw    = _norm01(profiles["combined_profile"])
        H           = len(inter_raw)
        curve_idx   = np.arange(H, dtype=np.float32)

        # gap_raw: intervertebral supera boundary → probable espacio entre vértebras
        gap_raw    = _norm01(np.clip(inter_raw - 0.35 * bnd_raw, 0.0, 1.0))
        gap_smooth = _norm01(_gf(gap_raw, sigma=smooth_sigma))
        comb_smooth = _norm01(_gf(comb_raw, sigma=smooth_sigma))

        # ── Peaks ──────────────────────────────────────────────────────
        _kw = {"distance": distance, "prominence": prominence}
        peaks,     peak_props = _fp(inter_raw,  **_kw)
        gap_peaks, gap_props  = _fp(gap_smooth, **_kw)

        # ── Espaciado de gaps ──────────────────────────────────────────
        if len(gap_peaks) >= 2:
            spacings         = np.diff(curve_idx[gap_peaks]).astype(np.float32)
            mean_gap_spacing = float(np.mean(spacings))
            std_gap_spacing  = float(np.std(spacings))
        else:
            mean_gap_spacing = float("nan")
            std_gap_spacing  = float("nan")

        vertebra_type = _classify_gap_spacing(len(gap_peaks), mean_gap_spacing)

        # ── DataFrame de perfil ────────────────────────────────────────
        is_peak     = np.zeros(H, dtype=np.int8)
        is_gap_peak = np.zeros(H, dtype=np.int8)
        if len(peaks):      is_peak[peaks]         = 1
        if len(gap_peaks):  is_gap_peak[gap_peaks] = 1

        df_profile = pd.DataFrame({
            "curve_idx":               curve_idx.astype(int),
            "inter_profile":           inter_raw,
            "boundary_profile":        bnd_raw,
            "combined_profile":        comb_raw,
            "profile_gap_score_raw":   gap_raw,
            "profile_gap_score_smooth": gap_smooth,
            "profile_combined_smooth":  comb_smooth,
            "is_peak":                 is_peak,
            "is_gap_peak":             is_gap_peak,
        })
        df_profile["patient_key"]      = patient_key
        df_profile["vertebra_type"]    = vertebra_type
        df_profile["n_peaks"]          = int(len(peaks))
        df_profile["n_gap_peaks"]      = int(len(gap_peaks))
        df_profile["mean_gap_spacing"] = mean_gap_spacing
        df_profile["std_gap_spacing"]  = std_gap_spacing

        # ── DataFrame de eventos ───────────────────────────────────────
        peak_prom = peak_props.get("prominences", np.zeros(len(peaks)))
        gap_prom  = gap_props.get("prominences",  np.zeros(len(gap_peaks)))

        rows: list[dict] = []
        for i, pk in enumerate(peaks):
            rows.append({
                "patient_key": patient_key,
                "kind":        "peak",
                "idx":         int(pk),
                "curve_idx":   float(curve_idx[pk]),
                "value":       float(inter_raw[pk]),
                "prominence":  float(peak_prom[i]) if i < len(peak_prom) else float("nan"),
            })
        for i, pk in enumerate(gap_peaks):
            rows.append({
                "patient_key": patient_key,
                "kind":        "gap_peak",
                "idx":         int(pk),
                "curve_idx":   float(curve_idx[pk]),
                "value":       float(gap_smooth[pk]),
                "prominence":  float(gap_prom[i]) if i < len(gap_prom) else float("nan"),
            })
        df_events = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(
                columns=["patient_key", "kind", "idx", "curve_idx", "value", "prominence"]
            )
        )

        # ── Completar columnas esperadas en df_events ──────────────────
        if len(df_events) > 0:
            df_events = df_events.sort_values("curve_idx").reset_index(drop=True)
            df_events["vertebra_id"]     = np.arange(1, len(df_events) + 1, dtype=np.int32)
            df_events["peak_height"]     = df_events["value"].astype(np.float32)
            df_events["wavelength_prev"] = df_events["curve_idx"].diff().fillna(0.0).astype(np.float32)
            df_events["wavelength_next"] = df_events["curve_idx"].diff(-1).abs().fillna(0.0).astype(np.float32)
            _win = 5
            _gap_str: list[float] = []
            for _, _ev in df_events.iterrows():
                if _ev["kind"] == "gap_peak":
                    _lo = max(0, int(_ev["idx"]) - _win)
                    _hi = min(H, int(_ev["idx"]) + _win + 1)
                    _gap_str.append(float(gap_smooth[_lo:_hi].mean()))
                else:
                    _gap_str.append(float("nan"))
            df_events["gap_strength_mean"] = _gap_str
        else:
            for _col in ["vertebra_id", "peak_height", "wavelength_prev",
                          "wavelength_next", "gap_strength_mean"]:
                df_events[_col] = pd.Series(dtype=np.float32)

        # ── Guardar CSVs ───────────────────────────────────────────────
        out_dir.mkdir(parents=True, exist_ok=True)
        profile_csv  = out_dir / f"{patient_key}_gap_peak_profile.csv"
        peaks_csv    = out_dir / f"{patient_key}_gap_peak_events.csv"
        summary_csv  = out_dir / f"{patient_key}_gap_peak_summary.csv"
        vertebra_csv = out_dir.parent / "vertebra_gap_peak_analysis.csv"  # alias para dataset builder
        fig_path     = out_dir / f"{patient_key}_gap_peak_analysis.png"

        summary = {
            "patient_key":      patient_key,
            "status":           "ok",
            "n_points":         H,
            "n_peaks":          int(len(peaks)),
            "n_gap_peaks":      int(len(gap_peaks)),
            "mean_gap_spacing": mean_gap_spacing,
            "std_gap_spacing":  std_gap_spacing,
            "vertebra_type":    vertebra_type,
            "profile_csv":      str(profile_csv),
            "peaks_csv":        str(peaks_csv),
            "summary_csv":      str(summary_csv),
            "vertebra_csv":     str(vertebra_csv),
            "figure_path":      str(fig_path),
        }

        df_profile.to_csv(str(profile_csv), index=False)
        df_events.to_csv(str(peaks_csv),    index=False)
        df_events.to_csv(str(vertebra_csv), index=False)  # alias compatible con build_patient_region_spatial_metrics_dataset
        pd.DataFrame([summary]).to_csv(str(summary_csv), index=False)

        # ── Figura ─────────────────────────────────────────────────────
        fig, ax = plt.subplots(1, 1, figsize=(14, 5))

        ax.plot(curve_idx, inter_raw,    label="intervertebral (norm)", alpha=0.7,  color="#4CAF50")
        ax.plot(curve_idx, bnd_raw,      label="boundary (norm)",       alpha=0.7,  color="#2196F3")
        ax.plot(curve_idx, gap_smooth,   label="gap smooth",            linewidth=2, color="#FF9800")
        ax.plot(curve_idx, comb_smooth,  label="combined smooth",       linewidth=1.5, color="#9C27B0")

        if len(peaks):
            ax.scatter(
                curve_idx[peaks], inter_raw[peaks],
                s=25, color="#F44336", zorder=5, label=f"peaks ({len(peaks)})",
            )
        if len(gap_peaks):
            ax.scatter(
                curve_idx[gap_peaks], gap_smooth[gap_peaks],
                s=35, color="#FF5722", zorder=5, marker="^",
                label=f"gap peaks ({len(gap_peaks)})",
            )

        ax.set_title(
            f"{patient_key} | gap_peaks={len(gap_peaks)} | type={vertebra_type}",
            fontsize=9,
        )
        ax.set_xlabel("Fila (px)")
        ax.set_ylabel("Señal normalizada")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7)

        plt.tight_layout()
        fig.savefig(str(fig_path), dpi=160, bbox_inches="tight")
        if plots_show:
            plt.show()
        plt.close(fig)

        return {**summary, "df_profile": df_profile, "df_events": df_events}

    # ------------------------------------------------------------------
    # Índice espacial: curva, centroides, peaks, matches
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_curve_from_binary(
        binary: np.ndarray,
        n_points: int = 240,
        thr: float = 0.30,
    ) -> pd.DataFrame | None:
        """Curva central por fila (media de x en píxeles con binary > thr)."""
        import pandas as pd

        binary = _normalize01_img(binary)
        ys_pix, xs_pix = np.where(binary > thr)
        if len(xs_pix) == 0:
            return None
        H, W = binary.shape
        curve_ys = np.linspace(float(ys_pix.min()), float(ys_pix.max()), n_points)
        curve_xs: list[float] = []
        for yy in curve_ys:
            row_x = xs_pix[np.abs(ys_pix - int(round(float(yy)))) < 4]
            curve_xs.append(
                float(np.mean(row_x)) if len(row_x) > 0
                else (curve_xs[-1] if curve_xs else float(W // 2))
            )
        curve_xs_arr = cv2.GaussianBlur(
            np.array(curve_xs, dtype=np.float32).reshape(-1, 1), (1, 11), 0,
        ).ravel()
        curve_ys_arr = np.array(curve_ys, dtype=np.float32)
        dx = np.diff(curve_xs_arr, prepend=curve_xs_arr[0])
        dy = np.diff(curve_ys_arr, prepend=curve_ys_arr[0])
        arc_length = np.cumsum(np.sqrt(dx**2 + dy**2))
        total = float(arc_length[-1]) or 1.0
        return pd.DataFrame({
            "curve_idx": np.arange(len(curve_xs_arr)),
            "x_curve":   curve_xs_arr,
            "y_curve":   curve_ys_arr,
            "arc_length": arc_length,
            "t_norm":    arc_length / total,
        })

    @staticmethod
    def _extract_centroids_from_ordered_mask(
        ordered_mask: np.ndarray,
        min_area: int = 25,
    ) -> pd.DataFrame:
        """Centroides por label de ordered_vertebra_mask."""
        import pandas as pd

        ordered_mask = np.asarray(ordered_mask)
        rows: list[dict] = []
        for lab in sorted([int(x) for x in np.unique(ordered_mask) if int(x) > 0]):
            m = ordered_mask == lab
            if int(m.sum()) < min_area:
                continue
            ys, xs = np.where(m)
            rows.append({
                "vertebra_id": int(lab),
                "centroid_x":  float(xs.mean()),
                "centroid_y":  float(ys.mean()),
                "area_px":     int(m.sum()),
                "bbox_x1": int(xs.min()), "bbox_x2": int(xs.max()),
                "bbox_y1": int(ys.min()), "bbox_y2": int(ys.max()),
            })
        return pd.DataFrame(rows)

    @staticmethod
    def _extract_centroids_from_binary_components(
        binary: np.ndarray,
        min_area: int = 25,
    ) -> pd.DataFrame:
        """Centroides por componentes conectadas (fallback sin ordered mask)."""
        import pandas as pd

        mask = (_normalize01_img(binary) > 0.35).astype(np.uint8)
        n, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        rows: list[dict] = []
        for lab in range(1, n):
            area = int(stats[lab, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            cx, cy = centroids[lab]
            rows.append({
                "vertebra_id": len(rows) + 1,
                "centroid_x":  float(cx),
                "centroid_y":  float(cy),
                "area_px":     area,
                "bbox_x1": int(stats[lab, cv2.CC_STAT_LEFT]),
                "bbox_y1": int(stats[lab, cv2.CC_STAT_TOP]),
                "bbox_x2": int(stats[lab, cv2.CC_STAT_LEFT] + stats[lab, cv2.CC_STAT_WIDTH]),
                "bbox_y2": int(stats[lab, cv2.CC_STAT_TOP] + stats[lab, cv2.CC_STAT_HEIGHT]),
            })
        df = pd.DataFrame(rows)
        if len(df) > 0:
            df = df.sort_values("centroid_y").reset_index(drop=True)
            df["vertebra_id"] = np.arange(1, len(df) + 1, dtype=np.int32)
        return df

    @staticmethod
    def _project_points_to_curve(
        points_df: pd.DataFrame,
        df_curve: pd.DataFrame,
        x_col: str,
        y_col: str,
        prefix: str,
    ) -> pd.DataFrame:
        """Proyecta puntos al punto más cercano de la curva (distancia Euclidea)."""
        import pandas as pd

        if points_df is None or len(points_df) == 0:
            return pd.DataFrame()
        curve_xy = df_curve[["x_curve", "y_curve"]].values.astype(np.float32)
        rows: list[dict] = []
        for _, r in points_df.iterrows():
            x, y = float(r[x_col]), float(r[y_col])
            d = np.sqrt((curve_xy[:, 0] - x)**2 + (curve_xy[:, 1] - y)**2)
            j = int(np.argmin(d))
            out = dict(r)
            out[f"{prefix}_curve_idx"]         = j
            out[f"{prefix}_curve_x"]           = float(df_curve.loc[j, "x_curve"])
            out[f"{prefix}_curve_y"]           = float(df_curve.loc[j, "y_curve"])
            out[f"{prefix}_arc_length"]        = float(df_curve.loc[j, "arc_length"])
            out[f"{prefix}_t_norm"]            = float(df_curve.loc[j, "t_norm"])
            out[f"{prefix}_distance_to_curve"] = float(d[j])
            rows.append(out)
        return pd.DataFrame(rows)

    @staticmethod
    def _match_centroids_to_peaks(
        df_centroids_proj: pd.DataFrame,
        df_peaks_proj: pd.DataFrame,
        max_arc_dist: float = 18.0,
    ) -> pd.DataFrame:
        """Empata cada centroide con el peak más cercano en arc_length."""
        import pandas as pd

        if len(df_centroids_proj) == 0 or len(df_peaks_proj) == 0:
            return pd.DataFrame()
        rows: list[dict] = []
        for _, c in df_centroids_proj.iterrows():
            ca = float(c["centroid_arc_length"])
            best, best_dist = None, float("inf")
            for _, p in df_peaks_proj.iterrows():
                dist = abs(ca - float(p["peak_arc_length"]))
                if dist < best_dist:
                    best_dist, best = dist, p
            out = dict(c)
            if best is not None and best_dist <= max_arc_dist:
                out.update({
                    "matched_peak_id":            int(best["peak_id"]),
                    "matched_peak_curve_idx":     int(best["peak_curve_idx"]),
                    "matched_peak_x":             float(best["peak_x"]),
                    "matched_peak_y":             float(best["peak_y"]),
                    "matched_peak_value":         float(best.get("peak_value", float("nan"))),
                    "centroid_peak_arc_distance": float(best_dist),
                    "centroid_peak_xy_distance":  float(
                        np.sqrt(
                            (float(c["centroid_x"]) - float(best["peak_x"]))**2 +
                            (float(c["centroid_y"]) - float(best["peak_y"]))**2
                        )
                    ),
                    "match_status": "matched",
                })
            else:
                out.update({
                    "matched_peak_id":            float("nan"),
                    "matched_peak_curve_idx":     float("nan"),
                    "matched_peak_x":             float("nan"),
                    "matched_peak_y":             float("nan"),
                    "matched_peak_value":         float("nan"),
                    "centroid_peak_arc_distance": float("nan"),
                    "centroid_peak_xy_distance":  float("nan"),
                    "match_status":               "no_peak_nearby",
                })
            rows.append(out)
        df_match = pd.DataFrame(rows)
        if len(df_match) > 0:
            df_match = df_match.sort_values("centroid_arc_length").reset_index(drop=True)
            df_match["spatial_order"]              = np.arange(1, len(df_match) + 1, dtype=np.int32)
            df_match["prev_centroid_arc_length"]   = df_match["centroid_arc_length"].shift(1)
            df_match["next_centroid_arc_length"]   = df_match["centroid_arc_length"].shift(-1)
            df_match["arc_dist_prev_centroid"]     = (
                df_match["centroid_arc_length"] - df_match["prev_centroid_arc_length"]
            )
            df_match["arc_dist_next_centroid"]     = (
                df_match["next_centroid_arc_length"] - df_match["centroid_arc_length"]
            )
        return df_match

    @staticmethod
    def _build_spatial_index(
        image: np.ndarray,
        binary_map: np.ndarray,
        gap_analysis: dict,
        patient_key: str,
        out_dir: Path,
        plots_show: bool = False,
        ordered_mask: np.ndarray | None = None,
        cfg: dict | None = None,
    ) -> dict:
        """
        Indexación espacial: curva + centroides + peaks + matches.
        Equivalente a ``build_spatial_index_for_patient`` del cuaderno.

        Usa datos en memoria del pipeline (no lee archivos).
        Peaks: gap_peaks de ``gap_analysis["df_events"]``.
        Centroides: de ``ordered_mask`` si se provee, si no de componentes de ``binary_map``.
        Siempre guarda CSVs y panel PNG en ``out_dir``; muestra si ``plots_show``.
        """
        import matplotlib.pyplot as plt
        import pandas as pd

        _cfg = {
            "curve_points": 240,
            "binary_thr_for_curve": 0.30,
            "binary_thr_for_centroids": 0.15,
            "max_arc_distance_peak_centroid": 18.0,
            "min_component_area": 25,
        }
        if cfg is not None:
            _cfg.update(cfg)
        out_dir.mkdir(parents=True, exist_ok=True)

        # ── 1) Curva ─────────────────────────────────────────────────
        df_curve = PatchReconstructionStage._compute_curve_from_binary(
            binary_map,
            n_points=int(_cfg["curve_points"]),
            thr=float(_cfg["binary_thr_for_curve"]),
        )
        if df_curve is None:
            raise ValueError(f"No se pudo calcular curva para {patient_key}")
        df_curve["patient_key"] = patient_key

        # ── 2) Centroides ─────────────────────────────────────────────
        if ordered_mask is not None:
            df_centroids = PatchReconstructionStage._extract_centroids_from_ordered_mask(
                ordered_mask, min_area=int(_cfg["min_component_area"]),
            )
            centroid_source = "ordered_mask"
        else:
            df_centroids = PatchReconstructionStage._extract_centroids_from_binary_components(
                binary_map, min_area=int(_cfg["min_component_area"]),
            )
            centroid_source = "binary_components"
        if len(df_centroids) > 0:
            df_centroids["patient_key"]     = patient_key
            df_centroids["centroid_source"] = centroid_source

        # ── 3) Peaks de gap_analysis ──────────────────────────────────
        df_events = gap_analysis.get("df_events", pd.DataFrame())
        df_peaks  = pd.DataFrame()
        if len(df_events) > 0:
            gap_rows = df_events[df_events["kind"] == "gap_peak"].copy()
            if len(gap_rows) > 0:
                peak_xs: list[float] = []
                for _, ev in gap_rows.iterrows():
                    y_t   = float(ev["curve_idx"])
                    idx_c = int(np.argmin(np.abs(df_curve["y_curve"].values - y_t)))
                    peak_xs.append(float(df_curve.loc[idx_c, "x_curve"]))
                gap_rows = gap_rows.copy()
                gap_rows["peak_x"]  = peak_xs
                gap_rows["peak_y"]  = gap_rows["curve_idx"].astype(float)
                gap_rows["peak_id"] = np.arange(1, len(gap_rows) + 1, dtype=np.int32)
                _keep = [c for c in ["patient_key", "peak_id", "curve_idx",
                                      "peak_x", "peak_y", "value"] if c in gap_rows.columns]
                df_peaks = gap_rows[_keep].rename(
                    columns={"curve_idx": "peak_curve_idx_raw", "value": "peak_value"}
                )

        # ── 4) Proyectar a curva ───────────────────────────────────────
        df_centroids_proj = PatchReconstructionStage._project_points_to_curve(
            df_centroids, df_curve, "centroid_x", "centroid_y", "centroid",
        )
        df_peaks_proj = (
            PatchReconstructionStage._project_points_to_curve(
                df_peaks, df_curve, "peak_x", "peak_y", "peak",
            )
            if len(df_peaks) > 0
            else pd.DataFrame()
        )

        # ── 5) Match centroides ↔ peaks ────────────────────────────────
        df_match = PatchReconstructionStage._match_centroids_to_peaks(
            df_centroids_proj,
            df_peaks_proj,
            max_arc_dist=float(_cfg["max_arc_distance_peak_centroid"]),
        )

        # ── 6) Guardar CSVs ───────────────────────────────────────────
        df_curve.to_csv(str(out_dir / "curve_spatial_index.csv"), index=False)
        df_centroids_proj.to_csv(str(out_dir / "centroids_projected_to_curve.csv"), index=False)
        df_peaks_proj.to_csv(str(out_dir / "peaks_projected_to_curve.csv"), index=False)
        df_match.to_csv(str(out_dir / "centroid_peak_spatial_index.csv"), index=False)

        # ── 7) Panel visual ───────────────────────────────────────────
        base = image if image.ndim == 2 else image[:, :, 0]
        fig, axes = plt.subplots(1, 3, figsize=(18, 7))

        axes[0].imshow(base, cmap="gray")
        axes[0].plot(df_curve["x_curve"], df_curve["y_curve"], lw=2, color="#2196F3")
        if len(df_centroids_proj) > 0:
            axes[0].scatter(
                df_centroids_proj["centroid_x"], df_centroids_proj["centroid_y"],
                s=35, color="#4CAF50",
            )
            for _, r in df_centroids_proj.iterrows():
                axes[0].text(
                    float(r["centroid_x"]), float(r["centroid_y"]),
                    str(int(r["vertebra_id"])), color="yellow", fontsize=8,
                )
        axes[0].set_title("Curva + centroides", fontsize=9)
        axes[0].axis("off")

        axes[1].imshow(base, cmap="gray")
        axes[1].plot(df_curve["x_curve"], df_curve["y_curve"], lw=2, color="#2196F3")
        if len(df_peaks_proj) > 0:
            axes[1].scatter(
                df_peaks_proj["peak_x"], df_peaks_proj["peak_y"],
                s=35, color="#FF9800", marker="^",
            )
            for _, r in df_peaks_proj.iterrows():
                axes[1].text(
                    float(r["peak_x"]), float(r["peak_y"]),
                    str(int(r["peak_id"])), color="cyan", fontsize=8,
                )
        axes[1].set_title("Curva + peaks (gap)", fontsize=9)
        axes[1].axis("off")

        axes[2].imshow(base, cmap="gray")
        axes[2].plot(df_curve["x_curve"], df_curve["y_curve"], lw=2, color="#2196F3")
        if len(df_match) > 0:
            axes[2].scatter(
                df_match["centroid_x"], df_match["centroid_y"],
                s=35, color="#4CAF50", label="centroid",
            )
            good = df_match["match_status"] == "matched"
            if good.any():
                axes[2].scatter(
                    df_match.loc[good, "matched_peak_x"],
                    df_match.loc[good, "matched_peak_y"],
                    s=35, color="#FF5722", marker="^", label="peak",
                )
                for _, r in df_match.loc[good].iterrows():
                    axes[2].plot(
                        [float(r["centroid_x"]), float(r["matched_peak_x"])],
                        [float(r["centroid_y"]), float(r["matched_peak_y"])],
                        lw=1, color="#FFC107", alpha=0.7,
                    )
            for _, r in df_match.iterrows():
                axes[2].text(
                    float(r["centroid_x"]), float(r["centroid_y"]),
                    str(int(r["spatial_order"])), color="white", fontsize=9,
                )
        axes[2].set_title("Centroide ↔ peak matches", fontsize=9)
        axes[2].axis("off")
        axes[2].legend(fontsize=7)

        fig.suptitle(
            f"{patient_key} — indexación espacial curva · centroides · peaks", fontsize=11,
        )
        plt.tight_layout()
        panel_path = out_dir / "panel_spatial_index_curve_centroids_peaks.png"
        fig.savefig(str(panel_path), dpi=160, bbox_inches="tight")
        if plots_show:
            plt.show()
        plt.close(fig)

        n_matches = (
            int((df_match["match_status"] == "matched").sum())
            if len(df_match) > 0 else 0
        )
        return {
            "patient_key":  patient_key,
            "df_curve":     df_curve,
            "df_centroids": df_centroids_proj,
            "df_peaks":     df_peaks_proj,
            "df_match":     df_match,
            "panel_path":   str(panel_path),
            "n_centroids":  len(df_centroids_proj),
            "n_peaks_proj": len(df_peaks_proj),
            "n_matches":    n_matches,
        }


# ──────────────────────────────────────────────────────────────────────
# Funciones de módulo: dataset espacial multi-paciente
# ──────────────────────────────────────────────────────────────────────

def _compute_apex_relation(row: dict) -> dict:
    """
    Relaciona cada vértebra/región con apex, Cobb y CSVL del JSON de métricas.
    Usado por ``build_patient_region_spatial_metrics_dataset``.
    """
    import math

    def _notna(v: object) -> bool:
        try:
            return math.isfinite(float(v))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False

    apex_idx        = row.get("cobb_curve_metrics_i_apex_global")
    apex_lumbar_idx = row.get("cobb_curve_metrics_i_apex_lumbar")
    c_idx           = row.get("centroid_curve_idx")
    p_idx           = row.get("matched_peak_curve_idx")
    csvl_x          = row.get("csvl_x_px")
    centroid_x      = row.get("centroid_x")
    t               = row.get("centroid_t_norm")

    out: dict = {}
    out["dist_centroid_curve_idx_to_apex_global"] = (
        abs(float(c_idx) - float(apex_idx)) if _notna(apex_idx) and _notna(c_idx) else float("nan")
    )
    out["dist_centroid_curve_idx_to_apex_lumbar"] = (
        abs(float(c_idx) - float(apex_lumbar_idx))
        if _notna(apex_lumbar_idx) and _notna(c_idx) else float("nan")
    )
    out["dist_peak_curve_idx_to_apex_global"] = (
        abs(float(p_idx) - float(apex_idx)) if _notna(apex_idx) and _notna(p_idx) else float("nan")
    )
    out["dist_centroid_x_to_csvl_px"] = (
        abs(float(centroid_x) - float(csvl_x))
        if _notna(csvl_x) and _notna(centroid_x) else float("nan")
    )
    out["signed_centroid_x_minus_csvl_px"] = (
        float(centroid_x) - float(csvl_x)
        if _notna(csvl_x) and _notna(centroid_x) else float("nan")
    )
    if not _notna(t):
        out["curve_zone"] = "unknown"
    elif float(t) < 0.25:
        out["curve_zone"] = "upper"
    elif float(t) < 0.50:
        out["curve_zone"] = "upper_mid"
    elif float(t) < 0.75:
        out["curve_zone"] = "lower_mid"
    else:
        out["curve_zone"] = "lower"
    return out


def _classify_region_affection(row: dict) -> str:
    """
    Clasificación inicial de región afectada.
    Combina Cobb, dist. apex y tipo vertebral por peak/gap.
    """
    import math

    try:
        cobb = float(row.get("cobb_angle_deg") or 0)
    except (TypeError, ValueError):
        cobb = 0.0
    try:
        dist_apex = float(row.get("dist_centroid_curve_idx_to_apex_global") or math.nan)
    except (TypeError, ValueError):
        dist_apex = math.nan
    if not math.isfinite(dist_apex):
        dist_apex = 999999.0
    vtype = str(row.get("vertebra_type", ""))

    if cobb < 10:
        base = "normal_or_minimal"
    elif dist_apex <= 40:
        base = "apex_region"
    elif dist_apex <= 90:
        base = "peri_apex_region"
    else:
        base = "distal_region"

    if vtype in {"compressed", "weak_gap", "wide_or_missing_gap"}:
        base = base + "_structural_irregular"
    return base


def build_patient_region_spatial_metrics_dataset(
    patient_dirs_root: Path,
    metrics_json_root: Path | None = None,
    patient_keys: list[str] | None = None,
    save: bool = True,
    out_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Construye dataset multi-paciente combinando:
      - spatial_index/centroid_peak_spatial_index.csv  (de _build_spatial_index)
      - vertebra_gap_peak_analysis.csv                 (de _analyze_peaks_gaps)
      - metrics_*.json                                 (métricas radiográficas, opcional)

    Parameters
    ----------
    patient_dirs_root : directorio con subdirectorios por paciente (outputs/patch_reconstruction/).
    metrics_json_root : directorio con JSONs de métricas (opcional).
    patient_keys      : lista de claves a procesar; si None, todos los subdirectorios.
    save              : guardar CSV de salida.
    out_dir           : directorio de salida; por defecto ``patient_dirs_root / "datasets"``.

    Returns
    -------
    (df_dataset, df_errors)
    """
    import json
    import re
    import pandas as pd

    try:
        from tqdm.auto import tqdm as _tqdm  # type: ignore[import]
    except ImportError:
        def _tqdm(it, **_kw):  # type: ignore[misc]
            return it

    patient_dirs_root = Path(patient_dirs_root)
    _out = Path(out_dir) if out_dir else patient_dirs_root / "datasets"
    _out.mkdir(parents=True, exist_ok=True)

    if patient_keys is None:
        patient_keys = [p.name for p in sorted(patient_dirs_root.iterdir()) if p.is_dir()]

    def _pid(pk: str) -> int | None:
        m = re.search(r"(\d+)", str(pk))
        return int(m.group(1)) if m else None

    def _pclass(pk: str) -> str:
        return "normal" if pk.startswith("N_") else ("scoliosis" if pk.startswith("S_") else "unknown")

    def _load_metrics(pk: str) -> dict:
        base: dict = {"patient_key": pk, "patient_id": _pid(pk), "patient_class": _pclass(pk)}
        if metrics_json_root is None:
            return base
        pid = _pid(pk)
        if pid is None:
            return base
        candidates = [
            Path(metrics_json_root) / f"metrics_{pid}.json",
            Path(metrics_json_root) / f"metric_{pid}.json",
        ]
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            hits = sorted(Path(metrics_json_root).glob(f"*{pid}*.json"))
            path = hits[0] if hits else None
        if path is None:
            return base

        def _flat(d: dict, prefix: str = "") -> dict:
            out: dict = {}
            for k, v in d.items():
                kk = f"{prefix}_{k}" if prefix else k
                if isinstance(v, dict):
                    out.update(_flat(v, kk))
                elif isinstance(v, (list, tuple)):
                    out[kk] = json.dumps(v)
                else:
                    out[kk] = v
            return out

        with open(path, "r", encoding="utf-8") as fh:
            base.update(_flat(json.load(fh)))
        return base

    all_rows: list[pd.DataFrame] = []
    errors: list[dict] = []

    for pk in _tqdm(patient_keys, desc="Dataset espacial + métricas"):
        try:
            pdir = patient_dirs_root / pk
            spatial_csv = pdir / "spatial_index" / "centroid_peak_spatial_index.csv"
            gap_csv     = pdir / "vertebra_gap_peak_analysis.csv"

            if not spatial_csv.exists():
                errors.append({"patient_key": pk, "error": f"missing {spatial_csv}"})
                continue

            df = pd.read_csv(spatial_csv)
            if gap_csv.exists():
                df_gap = pd.read_csv(gap_csv)
                if "vertebra_id" in df_gap.columns:
                    merge_cols = [c for c in df_gap.columns if c != "patient_key"]
                    df = df.merge(
                        df_gap[["patient_key"] + merge_cols],
                        on=["patient_key", "vertebra_id"],
                        how="left",
                        suffixes=("", "_gap"),
                    )

            metrics = _load_metrics(pk)
            for k, v in metrics.items():
                df[k] = v

            rel_rows = [_compute_apex_relation(dict(r)) for _, r in df.iterrows()]
            df_rel   = pd.DataFrame(rel_rows)
            df = pd.concat([df.reset_index(drop=True), df_rel.reset_index(drop=True)], axis=1)

            df["region_affection_type"] = [
                _classify_region_affection(dict(r)) for _, r in df.iterrows()
            ]
            df["region_key"] = (
                df["patient_key"].astype(str)
                + "_V"
                + df["vertebra_id"].astype(int).astype(str).str.zfill(2)
            )
            df["has_spatial_index"]    = 1
            df["has_gap_peak_analysis"] = int(gap_csv.exists())
            all_rows.append(df)

        except Exception as exc:
            errors.append({"patient_key": pk, "error": repr(exc)})

    df_dataset = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    df_errors  = pd.DataFrame(errors)

    if save:
        df_dataset.to_csv(str(_out / "patient_region_spatial_metrics_dataset.csv"), index=False)
        df_errors.to_csv(str(_out / "patient_region_spatial_metrics_dataset_errors.csv"), index=False)

    return df_dataset, df_errors


def fill_missing_patient_region_dataset_with_zero(
    df: pd.DataFrame,
    save: bool = True,
    out_path: Path | None = None,
) -> pd.DataFrame:
    """
    Rellena NaN/Inf numéricos con 0 y strings vacíos con ``""``.
    Equivalente a ``fill_missing_patient_region_dataset_with_zero`` del cuaderno.
    """
    import pandas as pd  # noqa: F811

    df0 = df.copy()
    for c in df0.select_dtypes(include=[np.number]).columns:
        df0[c] = df0[c].replace([np.inf, -np.inf], np.nan).fillna(0)
    for c in df0.select_dtypes(include=["object"]).columns:
        df0[c] = df0[c].fillna("").replace("nan", "")
    for c in df0.select_dtypes(include=["bool"]).columns:
        df0[c] = df0[c].astype(int)
    if save and out_path is not None:
        df0.to_csv(str(Path(out_path)), index=False)
    return df0
