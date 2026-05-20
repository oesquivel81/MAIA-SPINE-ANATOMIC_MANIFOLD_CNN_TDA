"""
Carga del checkpoint best_binary_curve_model.pt en FastBinaryCurveUNet.

Uso:
    from pipeline_ml.cnn_curve import load_binary_curve_model
    model = load_binary_curve_model("/ruta/al/best_binary_curve_model.pt")
"""
from __future__ import annotations

from pathlib import Path

import torch

from .architecture import FastBinaryCurveUNet


def load_binary_curve_model(
    checkpoint_path: str | Path,
    in_channels: int = 1,
    base_ch: int = 24,
    device: str | torch.device | None = None,
) -> FastBinaryCurveUNet:
    """
    Carga ``FastBinaryCurveUNet`` desde un checkpoint ``.pt``.

    El checkpoint debe contener la clave ``model_state_dict``.
    Si el archivo no existe lanza ``FileNotFoundError``.

    Args:
        checkpoint_path: ruta al archivo ``.pt`` del checkpoint.
        in_channels:     canales de entrada del modelo (default 1).
        base_ch:         canales base del UNet (default 24).
        device:          dispositivo de destino. Si es ``None`` se
                         resuelve automáticamente: CUDA si disponible, CPU en caso contrario.

    Returns:
        Modelo en modo evaluación listo para inferencia.
    """
    path = Path(checkpoint_path)
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint no encontrado: {path}")

    # Detectar puntero Git LFS (empieza con "version https://git-lfs")
    header = path.read_bytes(27)
    if header.startswith(b"version https://git-lfs"):
        raise RuntimeError(
            f"El archivo '{path}' es un puntero Git LFS, no el modelo real.\n"
            "El modelo no fue subido al servidor LFS (GIT_LFS_SKIP_PUSH fue usado).\n"
            "Opciones:\n"
            "  1. Apunta 'binary_curve_model_path' al archivo real en Google Drive.\n"
            "  2. Sube el .pt a LFS: git lfs push origin <branch> --all\n"
            "     Luego en Colab: git lfs pull --include='...best_binary_curve_model.pt'"
        )

    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device)

    ckpt = torch.load(path, map_location=device, weights_only=False)

    if "model_state_dict" not in ckpt:
        raise KeyError(
            f"El checkpoint '{path.name}' no contiene 'model_state_dict'. "
            f"Claves disponibles: {list(ckpt.keys())}"
        )

    model = FastBinaryCurveUNet(in_channels=in_channels, base_ch=base_ch)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    model.eval()

    return model
