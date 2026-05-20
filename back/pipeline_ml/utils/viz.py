"""
Utilidades de visualización para el pipeline_ml.
Usadas principalmente desde celdas de Colab para inspección interactiva.
"""

from __future__ import annotations

import numpy as np

# Mapas de color por cabeza del StudentUNet1CH4Heads
# Deben coincidir con _HEAD_CMAPS en stages/student_patch.py
_HEAD_CMAPS: dict[str, str] = {
    "binary":         "hot",
    "boundary":       "coolwarm",
    "intervertebral": "viridis",
    "ordinal":        "plasma",
}


def show_student_heads_consistent(
    patches_input: "np.ndarray",
    preds_dict: "dict[str, np.ndarray]",
    max_patches: int = 8,
) -> None:
    """
    Visualiza cada parche de entrada junto con las 4 salidas del StudentUNet.

    Args:
        patches_input: Array [N, H, W] o [N, 1, H, W] — parches en float32 [0,1].
        preds_dict: Diccionario con probabilidades sigmoideas por cabeza::

            {
                "binary":         ndarray [N, H, W],
                "boundary":       ndarray [N, H, W],
                "intervertebral": ndarray [N, H, W],
                "ordinal":        ndarray [N, H, W],
            }

        max_patches: Número máximo de parches a mostrar.

    Colores por cabeza (coherentes con StudentPatchStage):
        - binary:         hot
        - boundary:       coolwarm
        - intervertebral: viridis
        - ordinal:        plasma
    """
    import matplotlib.pyplot as plt

    if patches_input.ndim == 4:
        patches_input = patches_input[:, 0]

    heads = list(preds_dict.keys())
    n = min(max_patches, patches_input.shape[0])
    ncols = 1 + len(heads)

    fig, axes = plt.subplots(n, ncols, figsize=(3 * ncols, 3 * n))

    if n == 1:
        axes = np.expand_dims(axes, axis=0)

    # Títulos de columnas
    axes[0, 0].set_title("Input", fontsize=8, fontweight="bold")
    for j, head in enumerate(heads, start=1):
        axes[0, j].set_title(head, fontsize=8, fontweight="bold")

    for i in range(n):
        axes[i, 0].imshow(patches_input[i], cmap="gray", vmin=0, vmax=1)
        axes[i, 0].set_ylabel(f"P{i}", fontsize=7)
        axes[i, 0].axis("off")

        for j, head in enumerate(heads, start=1):
            pred = np.squeeze(preds_dict[head][i])
            cmap = _HEAD_CMAPS.get(head, "viridis")

            axes[i, j].imshow(pred, cmap=cmap, vmin=0, vmax=1)
            axes[i, j].set_title(
                f"min={pred.min():.2f} max={pred.max():.2f}\nmean={pred.mean():.2f}",
                fontsize=6,
            )
            axes[i, j].axis("off")

    fig.suptitle("StudentUNet1CH4Heads — salidas por parche", fontsize=9)
    plt.tight_layout()
    plt.show()
