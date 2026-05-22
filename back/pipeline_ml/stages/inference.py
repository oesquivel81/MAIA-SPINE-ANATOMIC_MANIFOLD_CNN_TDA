from __future__ import annotations

"""InferenceStage
==============
Adapta ``MAIAClinicalProbabilisticClusterAnalyzer`` al patrón pipeline.
Equivalente al análisis clínico-probabilístico del cuaderno Colab.

Entrada  (payload requerido)
----------------------------
    patch_reconstruction_done  bool
    gap_analysis               dict  (de PatchReconstructionStage._analyze_peaks_gaps)
        ├─ df_profile           DataFrame  columnas: curve_idx, combined_profile,
        │                                   inter_profile, boundary_profile,
        │                                   profile_gap_score_smooth, profile_gap_score_raw
        ├─ df_events            DataFrame  columnas: patient_key, kind, idx, curve_idx,
        │                                   value, prominence, vertebra_id, peak_height,
        │                                   wavelength_prev, wavelength_next, gap_strength_mean
        ├─ n_peaks, n_gap_peaks, mean_gap_spacing, std_gap_spacing, vertebra_type
        └─ figure_path, profile_csv, peaks_csv, summary_csv, vertebra_csv
    spatial_index              dict  (de PatchReconstructionStage._build_spatial_index)
        ├─ df_match             DataFrame  centroides proyectados + matched peak
        └─ df_centroids, df_peaks, df_curve
    image                      ndarray H×W float32
    recon_maps                 dict[str, ndarray]

Salida   (payload añadido)
--------------------------
    inference                  dict  {
        cluster_predictions    DataFrame
        cluster_summary        DataFrame
        df_patient_summary     DataFrame
        df_region_report       DataFrame
        X_raw                  DataFrame
        cobb_angle_deg         float
        cobb_severity          str
        dominant_cluster_id    int
        n_clusters_detected    int
        curve_proxy            dict {y, x, local_angles_deg}
        json_path              str
        summary_csv_path       str
        regions_csv_path       str
        figure_path            str | None
    }
    inference_done             bool

Archivos guardados en outputs/inference/{patient_key}/
------------------------------------------------------
    cluster_predictions.csv
    cluster_summary.csv
    clinical_summary.csv
    clinical_regions.csv
    X_raw_features.csv
    clinical_payload.json
    clinical_probabilistic_plot.png  (solo si plots_show=True)
"""

import json
from pathlib import Path
from typing import Any

import numpy as np

from pipeline_ml.context import PipelineContext
from pipeline_ml.logger import PipelineLogger
from pipeline_ml.stages.base import PipelineStage
from pipeline_ml.utils.stage_report import StageReport


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_APEX_ESTIMATE_WINDOW = 8   # ventana local (px) para left/right gap strength


# ---------------------------------------------------------------------------
# Helpers de módulo
# ---------------------------------------------------------------------------

def _safe_float(x: Any, default: float = 0.0) -> float:
    """Convierte a float seguro; devuelve default si NaN/None/error."""
    try:
        import math
        v = float(x)
        return default if math.isnan(v) else v
    except Exception:
        return float(default)


def _classify_cobb_severity(cobb_deg: float) -> str:
    d = abs(float(cobb_deg))
    if d < 10:
        return "no_scoliosis_or_below_threshold"
    elif d < 20:
        return "mild"
    elif d < 40:
        return "moderate"
    return "severe"


def _infer_anatomic_region(t_norm: float) -> str:
    t = float(t_norm)
    if t < 0.25:
        return "upper_thoracic_probable"
    elif t < 0.55:
        return "thoracic_probable"
    elif t < 0.75:
        return "thoracolumbar_probable"
    return "lumbar_probable"


# ===========================================================================
# InferenceStage
# ===========================================================================

class InferenceStage(PipelineStage):
    """Análisis clínico-probabilístico basado en GMM sobre features de señal."""

    name = "inference"

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(
        self,
        payload: dict[str, Any],
        context: PipelineContext,
        logger: PipelineLogger,
    ) -> dict[str, Any]:

        if not payload.get("patch_reconstruction_done"):
            logger.warn("InferenceStage: patch_reconstruction_done=False → saltando etapa")
            payload["inference_done"] = False
            return payload

        gap_analysis:  dict = payload["gap_analysis"]
        spatial_index: dict = payload.get("spatial_index", {})
        image:  np.ndarray  = payload["image"]
        H, W = image.shape[:2]

        patient_key: str = context.metadata.get(
            "patient_key", context.metadata.get("patient_id", "patient")
        )
        plots_show: bool = bool(context.metadata.get("plots_show", False))

        out_dir = context.work_dir / "outputs" / "inference" / patient_key
        out_dir.mkdir(parents=True, exist_ok=True)

        # ── Cargar bundle ──────────────────────────────────────────────
        cluster_path: Path | None = None
        if len(context.assets.joblib_paths) > 2:
            cluster_path = Path(context.assets.joblib_paths[2])

        if cluster_path is None or not cluster_path.exists():
            logger.warn(
                f"InferenceStage: no se encontró joblib de clustering "
                f"(joblib_paths[2]={cluster_path}). Saltando predicción."
            )
            payload["inference_done"] = False
            return payload

        try:
            bundle = self._load_cluster_bundle(cluster_path)
        except Exception as exc:
            logger.warn(f"InferenceStage: {exc}")
            raise
        assert "feature_cols" in bundle, "bundle debe contener 'feature_cols'"
        assert "best_model"   in bundle, "bundle debe contener 'best_model'"
        feature_cols: list[str] = bundle["feature_cols"]

        # ── Construir features ─────────────────────────────────────────
        df_debug, X_raw = self._build_features(
            gap_analysis=gap_analysis,
            spatial_index=spatial_index,
            image_h=H,
            image_w=W,
            feature_cols=feature_cols,
            patient_key=patient_key,
            logger=logger,
        )

        if X_raw is None or len(X_raw) == 0:
            logger.warn("InferenceStage: no hay gap_peaks para predecir cluster.")
            payload["inference_done"] = False
            return payload

        # ── Transformar ────────────────────────────────────────────────
        X_in = self._apply_transform(X_raw, bundle, logger)

        # ── Predecir ───────────────────────────────────────────────────
        df_cluster_out, df_cluster_summary = self._predict_clusters(
            df_debug=df_debug,
            X_in=X_in,
            bundle=bundle,
        )

        # ── Reporte clínico ────────────────────────────────────────────
        result = self._build_clinical_report(
            df_cluster_out=df_cluster_out,
            df_cluster_summary=df_cluster_summary,
            X_raw=X_raw,
            gap_analysis=gap_analysis,
            patient_key=patient_key,
            image_w=W,
            out_dir=out_dir,
            plots_show=plots_show,
        )

        payload["inference"] = {
            "cluster_predictions": df_cluster_out,
            "cluster_summary":     df_cluster_summary,
            **result,
        }
        payload["inference_done"] = True

        # ── Propagar debug a inference ─────────────────────────────────
        payload["inference"]["debug_images"] = payload.get("debug_images", {})
        payload["inference"]["debug_csvs"]   = payload.get("debug_csvs",   {})

        logger.info(
            f"InferenceStage: cluster_id dominante={result['dominant_cluster_id']}, "
            f"cobb_aprox={result['cobb_angle_deg']:.1f}°, "
            f"n_clusters={result['n_clusters_detected']}"
        )
        return payload

    # ------------------------------------------------------------------
    # Carga del bundle
    # ------------------------------------------------------------------

    @staticmethod
    def _load_cluster_bundle(joblib_path: Path) -> dict:
        import joblib
        import pickle

        last_exc: Exception | None = None

        # Intento 1: joblib nativo
        try:
            return joblib.load(str(joblib_path))
        except Exception as e:
            last_exc = e

        # Intento 2: pickle con encoding latin-1 (compatibilidad Python 2)
        try:
            with open(str(joblib_path), "rb") as fh:
                return pickle.load(fh, encoding="latin-1")
        except Exception as e:
            last_exc = e

        # Intento 3: pickle con encoding bytes
        try:
            with open(str(joblib_path), "rb") as fh:
                return pickle.load(fh, encoding="bytes")
        except Exception as e:
            last_exc = e

        # Intento 4: dill (más robusto entre versiones)
        try:
            import dill  # type: ignore[import]
            with open(str(joblib_path), "rb") as fh:
                return dill.load(fh)
        except ImportError:
            pass  # dill no disponible
        except Exception as e:
            last_exc = e

        raise RuntimeError(
            f"No se pudo cargar el bundle de clustering desde '{joblib_path}'.\n"
            f"Error: {last_exc}\n"
            f"El archivo fue guardado con una version incompatible de joblib/Python.\n"
            f"Solucion — ejecutar en Colab en la sesion donde existe el bundle:\n"
            f"  import joblib\n"
            f"  bundle = <tu variable bundle en memoria>\n"
            f"  joblib.dump(bundle, '{joblib_path}')\n"
            f"O instalar dill:  !pip install dill"
        ) from last_exc

    # ------------------------------------------------------------------
    # Construcción de features
    # ------------------------------------------------------------------

    @staticmethod
    def _build_features(
        gap_analysis:  dict,
        spatial_index: dict,
        image_h:       int,
        image_w:       int,
        feature_cols:  list[str],
        patient_key:   str,
        logger:        PipelineLogger,
    ):
        """
        Construye X_raw con las features del contrato del GMM a partir de los
        datos en memoria del payload (gap_analysis + spatial_index).

        Mapeo Colab → pipeline
        ----------------------
        freq_df.y_full / y_crop         → df_profile.curve_idx
        freq_df.smooth_combined_profile → df_profile.profile_gap_score_smooth
        peaks_df                        → df_events[kind == "gap_peak"]
        peaks_df.smooth_value           → df_events.value
        peaks_df.spacing_to_next        → df_events.wavelength_next
        df_match (si existe)            → centroid_distance_to_curve,
                                          centroid_peak_xy_distance,
                                          centroid_arc_length
        """
        import pandas as pd

        df_profile: pd.DataFrame = gap_analysis["df_profile"]
        df_events:  pd.DataFrame = gap_analysis["df_events"]
        df_match:   pd.DataFrame | None = spatial_index.get("df_match")

        # Solo gap_peaks como filas de features
        gap_peak_df = (
            df_events[df_events["kind"] == "gap_peak"]
            .reset_index(drop=True)
        )

        if len(gap_peak_df) == 0:
            logger.warn("InferenceStage._build_features: df_events sin gap_peaks")
            return pd.DataFrame(), None

        smooth  = df_profile["profile_gap_score_smooth"].values.astype(np.float32)
        boundary = df_profile["boundary_profile"].values.astype(np.float32)
        inter    = df_profile["inter_profile"].values.astype(np.float32)
        ci_arr   = df_profile["curve_idx"].values.astype(np.float32)

        y_min   = float(ci_arr.min())
        y_max   = float(ci_arr.max())
        y_range = max(y_max - y_min, 1e-6)

        estimated_apex_idx = float(
            gap_peak_df.loc[gap_peak_df["value"].astype(float).idxmax(), "curve_idx"]
        )

        # Índice de df_match por vertebra_id
        match_by_vid: dict[int, Any] = {}
        if df_match is not None and len(df_match) > 0:
            for _, mr in df_match.iterrows():
                vid = int(mr.get("vertebra_id", -1))
                if vid >= 0:
                    match_by_vid[vid] = mr

        rows: list[dict] = []

        for i, pk_row in gap_peak_df.iterrows():
            ci_pk       = float(pk_row["curve_idx"])
            row_idx     = int(pk_row["idx"])
            vertebra_id = int(pk_row.get("vertebra_id", i + 1))

            win = _APEX_ESTIMATE_WINDOW
            la, lb = max(0, row_idx - win), row_idx
            ra, rb = row_idx + 1, min(len(smooth), row_idx + win + 1)
            loc_a  = max(0, row_idx - win)
            loc_b  = min(len(smooth), row_idx + win + 1)

            peak_height     = _safe_float(pk_row.get("peak_height", pk_row.get("value")))
            prominence      = _safe_float(pk_row.get("prominence"))
            wl_prev         = _safe_float(pk_row.get("wavelength_prev"))
            wl_next         = _safe_float(pk_row.get("wavelength_next"))
            gap_str_mean    = _safe_float(pk_row.get("gap_strength_mean"))

            left_gap  = float(smooth[la:lb].mean()) if lb > la else 0.0
            right_gap = float(smooth[ra:rb].mean()) if rb > ra else 0.0

            dist_apex    = abs(ci_pk - estimated_apex_idx)
            arc_len      = ci_pk - y_min
            t_norm       = arc_len / y_range

            # Enriquecer con spatial_index si está disponible
            centroid_dist_curve   = 0.0
            centroid_peak_xy_dist = 0.0
            if vertebra_id in match_by_vid:
                mr = match_by_vid[vertebra_id]
                centroid_dist_curve   = _safe_float(mr.get("cen_distance_to_curve", 0.0))
                centroid_peak_xy_dist = _safe_float(mr.get("centroid_peak_xy_distance", 0.0))
                _arc = mr.get("cen_arc_length")
                if _arc is not None:
                    arc_len   = _safe_float(_arc, arc_len)
                    dist_apex = abs(arc_len - estimated_apex_idx)

            rows.append({
                "cobb_angle_deg": 0.0,

                "dist_centroid_curve_idx_to_apex_global":  dist_apex,
                "dist_peak_curve_idx_to_apex_global":      dist_apex,
                "dist_centroid_curve_idx_to_apex_lumbar":  dist_apex,

                "centroid_distance_to_curve":  centroid_dist_curve,
                "centroid_peak_xy_distance":   centroid_peak_xy_dist,

                "gap_strength_mean":   gap_str_mean,
                "right_gap_strength":  right_gap,
                "left_gap_strength":   left_gap,

                "peak_highpass_value": prominence,
                "peak_height":         peak_height,
                "matched_peak_value":  peak_height,

                "num_points":            float(len(df_profile)),
                "n_total_gaps_patient":  float(len(gap_peak_df)),
                "n_total_peaks_patient": float(len(gap_peak_df)),

                "centroid_arc_length": arc_len,
                "wavelength_prev":     wl_prev,
                "wavelength_next":     wl_next,
                "right_width_to_gap":  wl_next / 2.0 if wl_next > 0 else 0.0,
                "left_width_to_gap":   wl_prev / 2.0 if wl_prev > 0 else 0.0,

                # Internas (no entran al modelo)
                "_patient_key":        patient_key,
                "_peak_idx":           int(i),
                "_curve_idx":          ci_pk,
                "_vertebra_id":        vertebra_id,
                "_centroid_t_norm":    t_norm,
                "_estimated_apex_idx": estimated_apex_idx,
                "_boundary_local_mean": float(boundary[loc_a:loc_b].mean()) if loc_b > loc_a else 0.0,
                "_inter_local_mean":   float(inter[loc_a:loc_b].mean())     if loc_b > loc_a else 0.0,
            })

        df_debug = pd.DataFrame(rows)

        for col in feature_cols:
            if col not in df_debug.columns:
                logger.warn(f"InferenceStage: feature '{col}' no calculada → 0.0")
                df_debug[col] = 0.0

        X_raw = df_debug[feature_cols].astype(np.float32)
        return df_debug, X_raw

    # ------------------------------------------------------------------
    # Transformar
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_transform(X_raw, bundle: dict, logger: PipelineLogger) -> np.ndarray:
        best_rep    = bundle.get("best_representation")
        best_tr     = bundle.get("best_transform")
        fitted_trs  = bundle.get("fitted_transforms", {})

        def _apply_one(t_obj, X):
            if hasattr(t_obj, "transform"):
                return t_obj.transform(X)
            if isinstance(t_obj, dict):
                Xt = X
                sc = t_obj.get("scaler")
                tr = t_obj.get("transformer")
                if sc is not None: Xt = sc.transform(Xt)
                if tr is not None: Xt = tr.transform(Xt)
                return Xt
            raise TypeError(f"Transform no soportado: {type(t_obj)}")

        if best_rep and best_rep in fitted_trs:
            return _apply_one(fitted_trs[best_rep], X_raw)
        if best_tr is not None:
            return _apply_one(best_tr, X_raw)

        logger.warn("InferenceStage: no se encontró transform → usando X_raw directo")
        return X_raw.values if hasattr(X_raw, "values") else X_raw

    # ------------------------------------------------------------------
    # Predecir
    # ------------------------------------------------------------------

    @staticmethod
    def _predict_clusters(df_debug, X_in: np.ndarray, bundle: dict):
        import pandas as pd

        model         = bundle["best_model"]
        cluster_ids   = model.predict(X_in)
        cluster_probs = model.predict_proba(X_in)

        df_out = df_debug.copy()
        df_out["cluster_id"]                  = cluster_ids
        df_out["cluster_probability_max"]     = cluster_probs.max(axis=1)
        df_out["cluster_probability_entropy"] = -np.sum(
            cluster_probs * np.log(cluster_probs + 1e-12), axis=1
        )
        for k in range(cluster_probs.shape[1]):
            df_out[f"prob_cluster_{k}"] = cluster_probs[:, k]

        df_summary = (
            df_out
            .groupby("cluster_id")
            .agg(
                n_regions         =("cluster_id",               "count"),
                mean_probability  =("cluster_probability_max",  "mean"),
                max_probability   =("cluster_probability_max",  "max"),
                mean_entropy      =("cluster_probability_entropy", "mean"),
                mean_curve_idx    =("_curve_idx",               "mean"),
                min_curve_idx     =("_curve_idx",               "min"),
                max_curve_idx     =("_curve_idx",               "max"),
                mean_t_norm       =("_centroid_t_norm",         "mean"),
                mean_gap_strength =("gap_strength_mean",        "mean"),
                mean_peak_height  =("peak_height",              "mean"),
            )
            .reset_index()
            .sort_values(["max_probability", "n_regions"], ascending=False)
        )

        return df_out, df_summary

    # ------------------------------------------------------------------
    # Reporte clínico
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_curve_proxy(gap_analysis: dict, image_w: int) -> tuple:
        """Genera curva proxy probabilística desde el perfil combinado suavizado."""
        df_profile = gap_analysis["df_profile"]
        y      = df_profile["curve_idx"].values.astype(np.float32)
        signal = df_profile["profile_gap_score_smooth"].values.astype(np.float32)

        x_center = image_w / 2.0
        signal_range = float(signal.max() - signal.min())
        if signal_range > 1e-8:
            s = (signal - signal.min()) / (signal_range + 1e-8)
        else:
            s = np.zeros_like(signal)

        # Dampen displacement for low-variance signals (flat/normal spines).
        # Signals with range < _FLAT_SIGNAL_THRESHOLD are treated as nearly flat,
        # reducing spurious Cobb estimates caused by normal disc-space variation.
        _FLAT_SIGNAL_THRESHOLD = 0.30
        strength = min(1.0, signal_range / _FLAT_SIGNAL_THRESHOLD)

        x      = x_center + (s - s.mean()) * (image_w * 0.08) * strength
        dx     = np.gradient(x)
        dy     = np.gradient(y)
        angles = np.degrees(np.arctan(dx / (dy + 1e-8)))

        return y, x, angles

    @staticmethod
    def _estimate_cobb(y: np.ndarray, angles: np.ndarray) -> dict:
        n = len(angles)
        if n < 10:
            return {"cobb_angle_deg": 0.0, "upper_angle_deg": 0.0,
                    "lower_angle_deg": 0.0, "upper_y": None, "lower_y": None,
                    "method": "insufficient_points"}

        upper_region = angles[: max(3, n // 3)]
        lower_region = angles[int(2 * n // 3):]
        upper_idx    = int(np.argmax(np.abs(upper_region)))
        lower_idx    = int(2 * n // 3 + np.argmax(np.abs(lower_region)))

        ua = float(angles[upper_idx])
        la = float(angles[lower_idx])

        return {
            "cobb_angle_deg":  float(abs(ua - la)),
            "upper_angle_deg": ua,
            "lower_angle_deg": la,
            "upper_y":         float(y[upper_idx]),
            "lower_y":         float(y[lower_idx]),
            "method":          "probabilistic_curve_angle_difference",
        }

    @staticmethod
    def _build_clinical_report(
        df_cluster_out,
        df_cluster_summary,
        X_raw,
        gap_analysis:  dict,
        patient_key:   str,
        image_w:       int,
        out_dir:       Path,
        plots_show:    bool,
    ) -> dict:
        import pandas as pd

        curve_y, curve_x, local_angles = InferenceStage._estimate_curve_proxy(
            gap_analysis, image_w
        )
        cobb_pack = InferenceStage._estimate_cobb(curve_y, local_angles)

        # ── Reporte por región ─────────────────────────────────────────
        region_rows: list[dict] = []
        for _, r in df_cluster_out.iterrows():
            t = _safe_float(r.get("_centroid_t_norm"))
            region_rows.append({
                "patient_key":              patient_key,
                "peak_idx":                 int(r.get("_peak_idx")),
                "curve_idx":                _safe_float(r.get("_curve_idx")),
                "t_norm":                   t,
                "vertebra_id":              int(r.get("_vertebra_id", 0)),
                "anatomic_region_probable": _infer_anatomic_region(t),
                "cluster_id":               int(r.get("cluster_id")),
                "cluster_probability":      _safe_float(r.get("cluster_probability_max")),
                "cluster_entropy":          _safe_float(r.get("cluster_probability_entropy")),
                "gap_strength_mean":        _safe_float(r.get("gap_strength_mean")),
                "peak_height":              _safe_float(r.get("peak_height")),
                "peak_highpass_value":      _safe_float(r.get("peak_highpass_value")),
                "left_gap_strength":        _safe_float(r.get("left_gap_strength")),
                "right_gap_strength":       _safe_float(r.get("right_gap_strength")),
                "wavelength_prev":          _safe_float(r.get("wavelength_prev")),
                "wavelength_next":          _safe_float(r.get("wavelength_next")),
            })
        df_region_report = pd.DataFrame(region_rows)

        dominant = (
            df_cluster_summary
            .sort_values(["n_regions", "max_probability"], ascending=False)
            .iloc[0]
        )

        patient_summary = {
            "patient_key":                       patient_key,
            "n_probable_gaps":                   int(len(df_cluster_out)),
            "n_probable_vertebral_regions":      int(len(df_cluster_out) + 1),
            "n_clusters_detected":               int(df_cluster_out["cluster_id"].nunique()),
            "dominant_cluster_id":               int(dominant["cluster_id"]),
            "dominant_cluster_n_regions":        int(dominant["n_regions"]),
            "dominant_cluster_mean_probability": _safe_float(dominant["mean_probability"]),
            "cluster_probability_mean":          _safe_float(df_cluster_out["cluster_probability_max"].mean()),
            "cluster_probability_min":           _safe_float(df_cluster_out["cluster_probability_max"].min()),
            "cluster_probability_max":           _safe_float(df_cluster_out["cluster_probability_max"].max()),
            "probabilistic_cobb_angle_deg":      _safe_float(cobb_pack["cobb_angle_deg"]),
            "probabilistic_cobb_severity":       _classify_cobb_severity(cobb_pack["cobb_angle_deg"]),
            "upper_angle_deg":                   _safe_float(cobb_pack["upper_angle_deg"]),
            "lower_angle_deg":                   _safe_float(cobb_pack["lower_angle_deg"]),
            "upper_y":                           cobb_pack["upper_y"],
            "lower_y":                           cobb_pack["lower_y"],
            "cobb_method":                       cobb_pack["method"],
            "clinical_warning":
                "Approximate probabilistic research output. Not a clinical diagnosis.",
        }

        payload_dict = {
            "patient_key":   patient_key,
            "input_type":    "probabilistic_frequency_features_without_anatomic_json",
            "patient_summary":   patient_summary,
            "cluster_summary":   df_cluster_summary.to_dict(orient="records"),
            "region_candidates": df_region_report.to_dict(orient="records"),
            "curve_proxy": {
                "y":                [float(v) for v in curve_y],
                "x":                [float(v) for v in curve_x],
                "local_angles_deg": [float(v) for v in local_angles],
            },
            "feature_contract": {
                "json_anatomic_required": False,
                "approximated_fields": [
                    "cobb_angle_deg",
                    "dist_centroid_curve_idx_to_apex_global",
                    "dist_peak_curve_idx_to_apex_global",
                    "dist_centroid_curve_idx_to_apex_lumbar",
                    "centroid_distance_to_curve",
                    "centroid_peak_xy_distance",
                ],
            },
        }

        # ── Guardar archivos ───────────────────────────────────────────
        json_path        = out_dir / f"{patient_key}_clinical_payload.json"
        summary_csv_path = out_dir / "clinical_summary.csv"
        regions_csv_path = out_dir / "clinical_regions.csv"

        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(payload_dict, fh, indent=2, ensure_ascii=False)

        pd.DataFrame([patient_summary]).to_csv(summary_csv_path, index=False)
        df_region_report.to_csv(regions_csv_path, index=False)
        df_cluster_out.to_csv(out_dir / "cluster_predictions.csv", index=False)
        df_cluster_summary.to_csv(out_dir / "cluster_summary.csv", index=False)
        X_raw.to_csv(out_dir / "X_raw_features.csv", index=False)

        # ── Visualización ──────────────────────────────────────────────
        figure_path: Path | None = None
        if plots_show:
            import matplotlib.pyplot as plt

            df_profile    = gap_analysis["df_profile"]
            smooth_signal = df_profile["profile_gap_score_smooth"].values
            y_axis        = df_profile["curve_idx"].values

            fig, axes = plt.subplots(1, 3, figsize=(18, 5))

            axes[0].plot(smooth_signal, y_axis, color="steelblue")
            axes[0].invert_yaxis()
            axes[0].set_title("Perfil probabilístico")
            axes[0].set_xlabel("señal gap")
            axes[0].set_ylabel("row (curve_idx)")

            axes[1].plot(curve_x, curve_y, color="darkorange")
            axes[1].invert_yaxis()
            axes[1].set_title("Curva proxy probabilística")
            axes[1].set_xlabel("x estimada")
            axes[1].set_ylabel("y")

            axes[2].plot(local_angles, curve_y, color="darkgreen")
            axes[2].invert_yaxis()
            axes[2].set_title(
                f"Cobb aprox={patient_summary['probabilistic_cobb_angle_deg']:.2f}°  "
                f"({patient_summary['probabilistic_cobb_severity']})"
            )
            axes[2].set_xlabel("ángulo local")
            axes[2].set_ylabel("y")

            plt.suptitle(
                f"{patient_key} — análisis clínico-probabilístico  "
                f"clusters={patient_summary['n_clusters_detected']}"
            )
            plt.tight_layout()

            figure_path = out_dir / f"{patient_key}_clinical_probabilistic_plot.png"
            plt.savefig(str(figure_path), dpi=180, bbox_inches="tight")
            plt.show()
            plt.close(fig)

        return {
            "df_patient_summary": pd.DataFrame([patient_summary]),
            "df_region_report":   df_region_report,
            "X_raw":              X_raw,
            "cobb_angle_deg":     _safe_float(cobb_pack["cobb_angle_deg"]),
            "cobb_severity":      _classify_cobb_severity(cobb_pack["cobb_angle_deg"]),
            "dominant_cluster_id":  int(dominant["cluster_id"]),
            "n_clusters_detected":  int(df_cluster_out["cluster_id"].nunique()),
            "curve_proxy": {
                "y":                [float(v) for v in curve_y],
                "x":                [float(v) for v in curve_x],
                "local_angles_deg": [float(v) for v in local_angles],
            },
            "json_path":         str(json_path),
            "summary_csv_path":  str(summary_csv_path),
            "regions_csv_path":  str(regions_csv_path),
            "figure_path":       str(figure_path) if figure_path else None,
        }

    # ------------------------------------------------------------------
    # describe_output
    # ------------------------------------------------------------------

    def describe_output(self, payload: dict[str, Any]) -> StageReport:
        report = StageReport(stage_name=self.name)
        inf = payload.get("inference", {})
        report.add("inference_done",               payload.get("inference_done"))
        report.add("inference.dominant_cluster_id", inf.get("dominant_cluster_id"))
        report.add("inference.n_clusters_detected", inf.get("n_clusters_detected"))
        report.add("inference.cobb_angle_deg",      inf.get("cobb_angle_deg"))
        report.add("inference.cobb_severity",       inf.get("cobb_severity"))
        report.add("inference.json_path",           inf.get("json_path"))
        report.add("inference.figure_path",         inf.get("figure_path"))
        ps = inf.get("df_patient_summary")
        if ps is not None and hasattr(ps, "__len__") and len(ps) > 0:
            report.add("inference.cluster_probability_mean",
                       ps.iloc[0].get("cluster_probability_mean"))
            report.add("inference.n_probable_gaps",
                       ps.iloc[0].get("n_probable_gaps"))
        return report
