
# ============================================================
# LOAD EXPERIMENT — ROBUST VERSION
# ------------------------------------------------------------
# Intenta cargar en este orden:
# 1) model_architecture.py + checkpoint state_dict
# 2) artifacts/model_cloudpickle.pkl
# 3) artifacts/model_torchscript.pt
# ============================================================

from pathlib import Path
import json
import traceback
import torch


def _torch_load_safe(path, device):
    try:
        return torch.load(
            path,
            map_location=device,
            weights_only=False,
        )
    except TypeError:
        return torch.load(
            path,
            map_location=device,
        )


def _find_checkpoint(experiment_dir):
    ckpt_dir = experiment_dir / "checkpoints"

    if not ckpt_dir.exists():
        return None

    ckpts = list(ckpt_dir.glob("*_checkpoint.pt"))

    if len(ckpts) == 0:
        return None

    return ckpts[0]


def _load_manifest(experiment_dir):
    manifest_path = experiment_dir / "configs" / "experiment_manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)

    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_experiment(experiment_dir, device=None):
    experiment_dir = Path(experiment_dir)

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    manifest = _load_manifest(experiment_dir)

    ckpt_path = _find_checkpoint(experiment_dir)
    ckpt = None

    if ckpt_path is not None:
        ckpt = _torch_load_safe(ckpt_path, device)

    errors = []

    # --------------------------------------------------------
    # 1) Intento normal: model_architecture.py
    # --------------------------------------------------------
    try:
        from model_architecture import build_model

        model_init_kwargs = manifest["model_init_kwargs"]
        model = build_model(model_init_kwargs)

        if ckpt is None:
            raise RuntimeError("No checkpoint found for model_architecture.py restore.")

        model.load_state_dict(ckpt["model_state_dict"], strict=True)
        model.to(device)
        model.eval()

        manifest["_loaded_with"] = "model_architecture.py"

        return model, manifest, ckpt

    except Exception as e:
        errors.append(
            "model_architecture.py failed:\n"
            + repr(e)
            + "\n"
            + traceback.format_exc()
        )

    # --------------------------------------------------------
    # 2) Fallback: cloudpickle modelo completo
    # --------------------------------------------------------
    try:
        import cloudpickle

        cloudpickle_path = experiment_dir / "artifacts" / "model_cloudpickle.pkl"

        if not cloudpickle_path.exists():
            raise FileNotFoundError(cloudpickle_path)

        with open(cloudpickle_path, "rb") as f:
            model = cloudpickle.load(f)

        model.to(device)
        model.eval()

        manifest["_loaded_with"] = "cloudpickle"

        return model, manifest, ckpt

    except Exception as e:
        errors.append(
            "cloudpickle failed:\n"
            + repr(e)
            + "\n"
            + traceback.format_exc()
        )

    # --------------------------------------------------------
    # 3) Fallback: TorchScript
    # --------------------------------------------------------
    try:
        torchscript_path = experiment_dir / "artifacts" / "model_torchscript.pt"

        if not torchscript_path.exists():
            raise FileNotFoundError(torchscript_path)

        model = torch.jit.load(
            str(torchscript_path),
            map_location=device,
        )

        model.eval()

        manifest["_loaded_with"] = "torchscript"

        return model, manifest, ckpt

    except Exception as e:
        errors.append(
            "torchscript failed:\n"
            + repr(e)
            + "\n"
            + traceback.format_exc()
        )

    raise RuntimeError(
        "No se pudo cargar el experimento con ningún método.\n\n"
        + "\n\n".join(errors)
    )
