from __future__ import annotations

import io
from typing import Any

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


class NormalizationPlotRenderer:
    """Genera figuras matplotlib para la trazabilidad de normalización.

    render_normalized_plot → MANDATORIO: siempre se genera y guarda en la
        carpeta de trazabilidad (camino A local/Colab y camino B S3).

    render_comparison_plot → OPCIONAL: se genera solo cuando la bandera
        normalization_trace_visualization_enabled está activa.
    """

    def render_normalized_plot(
        self,
        normalized: np.ndarray,
        stats: dict[str, float],
        profile_summary: dict[str, Any],
        trace_id: str = "",
    ) -> np.ndarray:
        """Plot mandatorio: visualización de la imagen normalizada con anotaciones.

        Returns:
            np.ndarray BGR (PNG renderizado a través de matplotlib/Agg).
        """
        fig, ax = plt.subplots(figsize=(6, 8))

        ax.imshow(normalized, cmap="gray", vmin=0, vmax=255, aspect="auto")
        ax.axis("off")

        title = f"Imagen Normalizada\n{trace_id}" if trace_id else "Imagen Normalizada"
        ax.set_title(title, fontsize=11, fontweight="bold", pad=8)

        stats_text = (
            f"mean={stats.get('mean', 0):.1f}   std={stats.get('std', 0):.1f}\n"
            f"p5={stats.get('p5', 0):.1f}       p95={stats.get('p95', 0):.1f}\n"
            f"min={stats.get('min', 0):.1f}      max={stats.get('max', 0):.1f}\n"
            f"shape: {normalized.shape[0]} × {normalized.shape[1]}"
        )

        profile_text = (
            f"perfil: {profile_summary.get('patient_key', 'unknown')}\n"
            f"modo: {profile_summary.get('normalization_mode', '-')}   "
            f"p_low={profile_summary.get('normalization_p_low', '-')}  "
            f"p_high={profile_summary.get('normalization_p_high', '-')}"
        )

        fig.text(
            0.5, 0.01,
            stats_text,
            ha="center", va="bottom",
            fontsize=8, family="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0f0f0", alpha=0.85),
        )
        fig.text(
            0.5, 0.13,
            profile_text,
            ha="center", va="bottom",
            fontsize=8, family="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#e8f4e8", alpha=0.85),
        )

        plt.tight_layout(rect=[0, 0.23, 1, 1])
        return self._fig_to_bgr(fig)

    def render_comparison_plot(
        self,
        original: np.ndarray,
        normalized: np.ndarray,
        input_stats: dict[str, float],
        output_stats: dict[str, float],
        profile_summary: dict[str, Any],
    ) -> np.ndarray:
        """Plot opcional: comparación original vs normalizado con tabla de métricas.

        Returns:
            np.ndarray BGR (PNG renderizado a través de matplotlib/Agg).
        """
        fig, axes = plt.subplots(1, 2, figsize=(13, 8))

        axes[0].imshow(original, cmap="gray", vmin=0, vmax=255, aspect="auto")
        axes[0].set_title("Original", fontsize=11, fontweight="bold")
        axes[0].axis("off")

        axes[1].imshow(normalized, cmap="gray", vmin=0, vmax=255, aspect="auto")
        axes[1].set_title(
            f"Normalizado\nperfil: {profile_summary.get('patient_key', 'unknown')}\n"
            f"modo: {profile_summary.get('normalization_mode', '-')}",
            fontsize=10, fontweight="bold",
        )
        axes[1].axis("off")

        metric_labels = ["mean", "std", "median", "p5", "p95", "min", "max"]
        header = f"{'métrica':<12}  {'antes':>8}  {'después':>8}  {'Δ':>8}"
        separator = "─" * 44
        rows = [header, separator]
        for key in metric_labels:
            before = input_stats.get(key, 0.0)
            after = output_stats.get(key, 0.0)
            delta = after - before
            rows.append(f"{key:<12}  {before:>8.2f}  {after:>8.2f}  {delta:>+8.2f}")

        table_text = "\n".join(rows)
        fig.text(
            0.5, 0.01,
            table_text,
            ha="center", va="bottom",
            fontsize=8, family="monospace",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#f0f0f0", alpha=0.85),
        )

        plt.tight_layout(rect=[0, 0.28, 1, 1])
        return self._fig_to_bgr(fig)

    @staticmethod
    def _fig_to_bgr(fig: plt.Figure) -> np.ndarray:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        arr = np.frombuffer(buf.read(), dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
