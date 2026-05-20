# pipeline_ml/cnn_curve

Submódulo de inferencia CNN para detección de columna vertebral en radiografías de escoliosis.  
Implementa la arquitectura **FastBinaryCurveUNet** extraída del cuaderno de entrenamiento
`experiments/colab/PIPELINE_COMPLETE_2_CNN_OLD_SHARDS_...ipynb` (bloque 12).

---

## Archivos

| Archivo | Descripción |
|---|---|
| `architecture.py` | Clases `FastDoubleConv` y `FastBinaryCurveUNet` |
| `loader.py` | Función `load_binary_curve_model()` — carga checkpoint `.pt` |
| `__init__.py` | Re-exporta ambas clases y la función |

---

## Arquitectura — FastBinaryCurveUNet

UNet simétrico de **3 niveles**, **1 canal de entrada**, **2 cabezas de salida**.

```
Entrada  [B, 1, H, W]
    │
    ├─ e1  FastDoubleConv(1  → 24)   ──────────────────────────────── skip s1
    │       MaxPool2d(2)
    ├─ e2  FastDoubleConv(24 → 48)   ─────────────────────── skip s2
    │       MaxPool2d(2)
    ├─ e3  FastDoubleConv(48 → 96)   ──────────── skip s3
    │       MaxPool2d(2)
    │
    ├─ b   FastDoubleConv(96 → 192)  ← bottleneck
    │
    ├─ u3  ConvTranspose2d(192→96)  + interpolate → cat(s3) → d3  FastDoubleConv(192→96)
    ├─ u2  ConvTranspose2d(96→48)   + interpolate → cat(s2) → d2  FastDoubleConv(96→48)
    ├─ u1  ConvTranspose2d(48→24)   + interpolate → cat(s1) → d1  FastDoubleConv(48→24)
    │
    ├─ head_binary  Conv2d(24→1, k=1)  → logits  [B,1,H,W]
    └─ head_curve   Conv2d(24→1, k=1)  → logits  [B,1,H,W]
```

### Bloque FastDoubleConv

```
Conv2d(in→out, k=3, pad=1, bias=False) → BN → ReLU
Conv2d(out→out, k=3, pad=1, bias=False) → BN → ReLU
```

Sub-módulo interno: `self.net` (Sequential). Las keys del state_dict tienen la forma
`e1.net.0.weight`, `e1.net.1.weight`, etc.

### Parámetros del modelo

| Hiperparámetro | Valor por defecto |
|---|---|
| `in_channels` | `1` |
| `base_ch` | `24` |
| Parámetros totales | ~1.25 M |

### Checkpoint esperado

El archivo `.pt` debe contener al menos la clave `model_state_dict`:

```python
{
    "model_state_dict": OrderedDict(...),  # obligatorio
    "epoch": int,                          # opcional
    "stage": str,                          # opcional
    "best_val_loss": float,                # opcional
}
```

Ruta en Colab (experimento `v02A`):
```
/content/MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA/experiments/v02A/pipeline_model/
    01_binary_curve_cnn/best_binary_curve_model.pt
```

---

## Uso

```python
from pipeline_ml.cnn_curve import load_binary_curve_model

model = load_binary_curve_model(
    "/ruta/al/best_binary_curve_model.pt",
    device="cuda",  # o "cpu", o None para autodetección
)

# Inferencia
import torch
tensor = torch.zeros(1, 1, 512, 512)   # [B, 1, H, W] float32 en [0,1]
with torch.no_grad():
    out = model(tensor)

binary_logits = out["binary"]  # [1,1,512,512]
curve_logits  = out["curve"]   # [1,1,512,512]

# Binarizar con umbral 0.5
import torch.nn.functional as F
binary_mask = (torch.sigmoid(binary_logits) >= 0.5).squeeze().cpu().numpy()
curve_mask  = (torch.sigmoid(curve_logits)  >= 0.5).squeeze().cpu().numpy()
```

---

## Validaciones en loader.py

`load_binary_curve_model()` aplica tres guardas antes de llamar `torch.load`:

1. **Existencia del archivo** — `FileNotFoundError` si la ruta no existe.
2. **Extensión** — `ValueError` si el archivo no es `.pt` / `.pth` (p.ej., se pasó un `.joblib`).
3. **Puntero Git LFS** — `RuntimeError` si el archivo empieza con `version https://git-lfs`
   (el modelo real no fue descargado del servidor LFS).

---

## Integración en el pipeline

`BinaryCurveStage` (`stages/binary_curve.py`) usa este submódulo:

- Lee la ruta del checkpoint desde `context.assets.joblib_paths[0]`
  (primer asset del string `full_assets` pasado al pipeline).
- Fallback: `config.paths.binary_curve_model_path`.
- Carga el modelo de forma **lazy** (solo la primera vez que se ejecuta el stage).
- Guarda las máscaras en `outputs/cnn_curve/binary_mask.png` y `outputs/cnn_curve/curve_mask.png`.

### String full_assets esperado

```
APELLIDO_NOMBRE|/ruta/best_binary_curve_model.pt;/ruta/student.joblib;/ruta/clustering.joblib|/ruta/r1.csv;/ruta/r2.json
```

---

## Fixes aplicados durante integración

| Commit | Descripción |
|---|---|
| `8bdacb9f0` | `path.read_bytes()[:27]` — `Path.read_bytes()` no acepta argumentos posicionales |
| `c1926d1ae` | Renombrar `.block` → `.net` y `up3/up2/up1` → `u3/u2/u1` para coincidir con keys del checkpoint guardado |
| `8a2e7538d` | Validar extensión `.pt/.pth` antes de `torch.load` con mensaje de error accionable |
