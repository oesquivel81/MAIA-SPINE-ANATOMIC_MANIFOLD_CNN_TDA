
# ============================================================
# FULL-RES INFERENCE FOR MAIA SPINE EXPERIMENT
# ============================================================

from pathlib import Path
import cv2
import numpy as np
import torch
import torch.nn.functional as F
import matplotlib.pyplot as plt

from load_experiment import load_experiment
from filters import FILTER_FUNCS


def read_gray_float01(path, resize_hw=None):
    path = Path(path)

    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

    if img is None:
        raise FileNotFoundError(path)

    img = img.astype(np.float32)

    if img.max() > 1.5:
        img = img / 255.0

    img = np.clip(img, 0.0, 1.0).astype(np.float32)

    if resize_hw is not None:
        h, w = resize_hw
        img = cv2.resize(
            img,
            (w, h),
            interpolation=cv2.INTER_AREA,
        )

    return img.astype(np.float32)


def build_x_channels(image_path, manifest):
    img_h = int(manifest["img_h"])
    img_w = int(manifest["img_w"])

    selected_filters = list(manifest.get("selected_filters", []))

    base = read_gray_float01(
        image_path,
        resize_hw=(img_h, img_w),
    )

    channels = [base.astype(np.float32)]

    for fname in selected_filters:
        if fname not in FILTER_FUNCS:
            raise KeyError(f"Filtro no soportado: {fname}")

        ch = FILTER_FUNCS[fname](base)
        ch = np.clip(ch, 0.0, 1.0).astype(np.float32)

        channels.append(ch)

    x = np.stack(channels, axis=0).astype(np.float32)

    expected = (
        int(manifest["n_input_channels"]),
        img_h,
        img_w,
    )

    if x.shape != expected:
        raise ValueError(
            f"x shape incorrecto {x.shape}, esperado {expected}"
        )

    return x


def colorize_region(mask, num_classes=25):
    mask = np.asarray(mask).astype(np.int64)

    cmap = plt.get_cmap("turbo", num_classes)
    rgb = cmap(np.clip(mask, 0, num_classes - 1))[..., :3]

    rgb[mask == 0] = 0.0

    return rgb.astype(np.float32)


def save_gray01(path, arr):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    arr = np.clip(np.asarray(arr, dtype=np.float32), 0, 1)
    u8 = (arr * 255.0).astype(np.uint8)

    cv2.imwrite(str(path), u8)


def save_rgb01(path, rgb):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rgb = np.clip(np.asarray(rgb, dtype=np.float32), 0, 1)
    rgb_u8 = (rgb * 255.0).astype(np.uint8)

    bgr = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(path), bgr)


def _resize_logits(logits, full_h, full_w):
    return F.interpolate(
        logits.float(),
        size=(full_h, full_w),
        mode="bilinear",
        align_corners=False,
    )


@torch.no_grad()
def infer_fullres(
    experiment_dir,
    image_path,
    output_dir,
    patient_key=None,
    threshold=0.5,
    device=None,
):
    experiment_dir = Path(experiment_dir)
    image_path = Path(image_path)
    output_dir = Path(output_dir)

    model, manifest, ckpt = load_experiment(
        experiment_dir=experiment_dir,
        device=device,
    )

    device = next(model.parameters()).device

    if patient_key is None:
        patient_key = image_path.stem

    patient_out = output_dir / str(patient_key)
    patient_out.mkdir(parents=True, exist_ok=True)

    full_img = read_gray_float01(
        image_path,
        resize_hw=None,
    )

    full_h, full_w = full_img.shape[:2]

    x = build_x_channels(
        image_path=image_path,
        manifest=manifest,
    )

    x_t = torch.from_numpy(x[None]).float().to(device)

    model.eval()
    out = model(x_t)

    required_heads = [
        "region",
        "binary",
        "boundary",
        "intervertebral",
        "curve",
    ]

    for h in required_heads:
        if h not in out:
            raise KeyError(
                f"El modelo no devolvió head '{h}'. Heads disponibles: {list(out.keys())}"
            )

    region_logits = _resize_logits(out["region"], full_h, full_w)
    binary_logits = _resize_logits(out["binary"], full_h, full_w)
    boundary_logits = _resize_logits(out["boundary"], full_h, full_w)
    inter_logits = _resize_logits(out["intervertebral"], full_h, full_w)
    curve_logits = _resize_logits(out["curve"], full_h, full_w)

    region_pred = torch.argmax(
        region_logits,
        dim=1,
    )[0].detach().cpu().numpy().astype(np.uint8)

    binary_prob = torch.sigmoid(binary_logits)[0, 0].detach().cpu().numpy().astype(np.float32)
    boundary_prob = torch.sigmoid(boundary_logits)[0, 0].detach().cpu().numpy().astype(np.float32)
    inter_prob = torch.sigmoid(inter_logits)[0, 0].detach().cpu().numpy().astype(np.float32)
    curve_prob = torch.sigmoid(curve_logits)[0, 0].detach().cpu().numpy().astype(np.float32)

    binary_mask = (binary_prob >= threshold).astype(np.float32)

    base_rgb = np.stack(
        [full_img, full_img, full_img],
        axis=-1,
    ).astype(np.float32)

    region_rgb = colorize_region(
        region_pred,
        num_classes=int(manifest["num_region_classes"]),
    )

    overlay_region = np.clip(
        0.65 * base_rgb + 0.35 * region_rgb,
        0,
        1,
    )

    overlay_boundary = base_rgb.copy()
    overlay_boundary[..., 0] = np.maximum(
        overlay_boundary[..., 0],
        boundary_prob,
    )

    overlay_curve = base_rgb.copy()
    overlay_curve[..., 0] = np.maximum(
        overlay_curve[..., 0],
        curve_prob,
    )
    overlay_curve[..., 1] = np.maximum(
        overlay_curve[..., 1],
        curve_prob,
    )

    save_gray01(patient_out / "00_full_image.png", full_img)

    cv2.imwrite(
        str(patient_out / "01_region_pred_0_24.png"),
        region_pred.astype(np.uint8),
    )

    save_rgb01(patient_out / "02_region_pred_color.png", region_rgb)
    save_gray01(patient_out / "03_binary_prob.png", binary_prob)
    save_gray01(patient_out / "04_binary_mask.png", binary_mask)
    save_gray01(patient_out / "05_boundary_prob.png", boundary_prob)
    save_gray01(patient_out / "06_intervertebral_prob.png", inter_prob)
    save_gray01(patient_out / "07_curve_prob.png", curve_prob)

    save_rgb01(patient_out / "08_overlay_region.png", overlay_region)
    save_rgb01(patient_out / "09_overlay_boundary.png", overlay_boundary)
    save_rgb01(patient_out / "10_overlay_curve.png", overlay_curve)

    return {
        "patient_key": str(patient_key),
        "output_dir": str(patient_out),
        "full_h": int(full_h),
        "full_w": int(full_w),
        "input_shape": tuple(x.shape),
        "selected_filters": manifest.get("selected_filters", []),
        "loaded_with": manifest.get("_loaded_with"),
    }
