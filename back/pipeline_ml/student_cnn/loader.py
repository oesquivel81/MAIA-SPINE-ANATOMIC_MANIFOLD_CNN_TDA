"""
Carga del checkpoint student_1ch_4heads_boundary_rescue_final.pt
en StudentUNet1CH4Heads.

Uso:
    from pipeline_ml.student_cnn import load_student_patch_model
    model = load_student_patch_model("/ruta/al/student_1ch_4heads_boundary_rescue_final.pt")
"""
from __future__ import annotations

from pathlib import Path

import torch

from .architecture import StudentUNet1CH4Heads


def load_student_patch_model(
    checkpoint_path: str | Path,
    base: int = 16,
    dropout: float = 0.05,
    device: str | torch.device | None = None,
) -> StudentUNet1CH4Heads:
    """
    Carga ``StudentUNet1CH4Heads`` desde un checkpoint ``.pt``.

    El checkpoint debe contener la clave ``model_state_dict``.

    Args:
        checkpoint_path : ruta al archivo ``.pt`` del checkpoint.
        base            : canales base del UNet (default 16).
        dropout         : dropout del modelo (default 0.05).
        device          : dispositivo destino; si es ``None`` se resuelve
                          automáticamente (CUDA si disponible, CPU en caso contrario).

    Returns:
        Modelo en modo evaluación listo para inferencia.

    Raises:
        FileNotFoundError : si el archivo no existe.
        ValueError        : si la extensión no es ``.pt`` / ``.pth``.
        RuntimeError      : si el archivo es un puntero Git LFS.
        KeyError          : si el checkpoint no contiene ``model_state_dict``.
    """
    path = Path(checkpoint_path)

    if not path.exists():
        raise FileNotFoundError(f"Checkpoint no encontrado: {path}")

    if path.suffix.lower() not in {".pt", ".pth"}:
        raise ValueError(
            f"Se esperaba un archivo PyTorch (.pt / .pth) pero se recibió '{path.name}'.\n"
            "Verifica que 'student_patch_model_path' apunte al archivo .pt correcto."
        )

    # Detectar puntero Git LFS
    header = path.read_bytes()[:27]
    if header.startswith(b"version https://git-lfs"):
        raise RuntimeError(
            f"El archivo '{path}' es un puntero Git LFS, no el modelo real.\n"
            "El modelo no fue descargado desde LFS.\n"
            "Opciones:\n"
            "  1. Apunta 'student_patch_model_path' al archivo real en Google Drive.\n"
            "  2. Descarga: git lfs pull --include='*student_1ch_4heads*'"
        )

    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device)

    ckpt = torch.load(path, map_location=device, weights_only=False)

    if "model_state_dict" not in ckpt:
        raise KeyError(
            f"El checkpoint '{path.name}' no contiene la clave 'model_state_dict'.\n"
            f"Claves encontradas: {list(ckpt.keys())}"
        )

    model = StudentUNet1CH4Heads(base=base, dropout=dropout)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    model.eval()

    return model
