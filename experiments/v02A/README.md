# v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

## Experiment ID

```text
v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_035024
```

## Version

```text
v.02.A
```

## Input

```text
[B, 2, 256, 256]
```

## Selected filters

```text
['combined_v7']
```

## Main files

```text
checkpoints/
artifacts/
src/model_architecture.py
src/filters.py
src/load_experiment.py
src/inference_fullres.py
configs/experiment_manifest.json
requirements.txt
```

## Restore in another Colab

```python
!git clone --branch experiment/v02A https://github.com/oesquivel81/MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA.git
%cd MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA/experiments/v02A

!pip install -r requirements.txt

import sys
from pathlib import Path

sys.path.append(str(Path('src').resolve()))

from load_experiment import load_experiment

model, manifest, ckpt = load_experiment(
    experiment_dir=Path('.'),
    device='cuda'
)

print(manifest['experiment_version_tag'])
print(manifest.get('_loaded_with'))
```

## Full-res inference

```python
from inference_fullres import infer_fullres

result = infer_fullres(
    experiment_dir=Path('.'),
    image_path=Path('/content/image.png'),
    output_dir=Path('/content/fullres_output'),
    patient_key='test',
    device='cuda'
)

print(result)
```

## Configuration Block 

```python
============================================================

BLOQUE A — CONFIG FLEXIBLE DE LOSSES Y STAGES  ALAN-CONFIGURE

------------------------------------------------------------

Sistema flexible:

- Las etapas se definen por porcentaje.

- Puedes cambiar epochs sin reescribir ifs.

- Puedes mezclar losses por etapa.

- Puedes repetir etapas.

- Puedes crear ciclos de refinamiento.

============================================================

CFG.setdefault("epochs", 100)CFG.setdefault("lr", 1e-4)CFG.setdefault("weight_decay", 1e-5)CFG.setdefault("hard_topk_ratio", 0.20)CFG.setdefault("grad_clip", 1.0)

------------------------------------------------------------

Loss keys disponibles

------------------------------------------------------------

LOSS_KEYS = [# Binary"binary_bce","binary_dice","binary_tversky","binary_topk",

# Boundary
"boundary_bce",
"boundary_dice",
"boundary_focal",
"boundary_tversky",
"boundary_topk",

# Region
"region_ce",
"region_dice",
"region_focal",
"region_topk",
"region_outside",

# Intervertebral
"inter_bce",
"inter_dice",
"inter_focal",
"inter_tversky",
"inter_topk",

# Curve
"curve_bce",
"curve_dice",
"curve_mse",

]

def zero_loss_weights():return {k: 0.0 for k in LOSS_KEYS}

def merge_loss_weights(*dicts):"""Mezcla varios diccionarios de losses.Los últimos pisan a los anteriores."""out = zero_loss_weights()

for d in dicts:
    if d is None:
        continue

    for k, v in d.items():
        if k not in out:
            print(f"[WARN] Loss key desconocida: {k}")
        out[k] = float(v)

return out

------------------------------------------------------------

Perfiles reutilizables de loss

------------------------------------------------------------

LOSS_PROFILES = {}

LOSS_PROFILES["binary_strong"] = {"binary_bce": 1.50,"binary_dice": 3.00,"binary_tversky": 1.50,"binary_topk": 0.80,"region_outside": 3.00,}

LOSS_PROFILES["binary_soft"] = {"binary_bce": 0.80,"binary_dice": 1.40,"binary_tversky": 0.60,"binary_topk": 0.20,"region_outside": 2.50,}

LOSS_PROFILES["boundary_strong"] = {"boundary_bce": 1.20,"boundary_dice": 2.80,"boundary_focal": 1.20,"boundary_tversky": 1.00,"boundary_topk": 0.80,}

LOSS_PROFILES["boundary_soft"] = {"boundary_bce": 0.50,"boundary_dice": 1.00,"boundary_focal": 0.40,"boundary_tversky": 0.40,"boundary_topk": 0.20,}

LOSS_PROFILES["region_strong"] = {"region_ce": 2.80,"region_dice": 2.40,"region_focal": 1.20,"region_topk": 1.00,"region_outside": 5.00,}

LOSS_PROFILES["region_soft"] = {"region_ce": 0.60,"region_dice": 0.40,"region_focal": 0.20,"region_topk": 0.10,"region_outside": 3.00,}

LOSS_PROFILES["inter_strong"] = {"inter_bce": 1.00,"inter_dice": 2.20,"inter_focal": 1.00,"inter_tversky": 1.00,"inter_topk": 0.70,}

LOSS_PROFILES["inter_soft"] = {"inter_bce": 0.25,"inter_dice": 0.40,"inter_focal": 0.20,"inter_tversky": 0.20,"inter_topk": 0.10,}

LOSS_PROFILES["curve_soft"] = {"curve_bce": 0.10,"curve_dice": 0.25,"curve_mse": 0.20,}

LOSS_PROFILES["curve_strong"] = {"curve_bce": 0.25,"curve_dice": 0.60,"curve_mse": 0.40,}

------------------------------------------------------------

Stage plan por porcentajes

------------------------------------------------------------

start_pct / end_pct están en [0,1].

Puedes cambiar CFG["epochs"] y se adapta solo.

------------------------------------------------------------

CFG["stage_plan"] = [{"name": "binary_foundation","start_pct": 0.00,"end_pct": 0.15,"profiles": ["binary_strong", "boundary_soft", "region_soft"],"lr_mult": 1.00,"hard_topk_ratio": 0.25,"grad_clip": 1.00,"note": "Aprender columna/fondo y limpiar background.",},{"name": "boundary_refine","start_pct": 0.15,"end_pct": 0.30,"profiles": ["binary_soft", "boundary_strong", "region_soft", "inter_soft"],"lr_mult": 0.90,"hard_topk_ratio": 0.25,"grad_clip": 1.00,"note": "Refinar bordes externos sin apagar binaria.",},{"name": "intervertebral_refine","start_pct": 0.30,"end_pct": 0.45,"profiles": ["binary_soft", "boundary_soft", "inter_strong", "region_soft"],"lr_mult": 0.85,"hard_topk_ratio": 0.20,"grad_clip": 1.00,"note": "Aprender separaciones internas entre regiones.",},{"name": "region_strong","start_pct": 0.45,"end_pct": 0.70,"profiles": ["binary_soft", "boundary_soft", "inter_soft", "region_strong"],"lr_mult": 0.75,"hard_topk_ratio": 0.20,"grad_clip": 1.00,"note": "Atacar colapso regional y estabilizar clases 1..24.",},{"name": "binary_boundary_reclean","start_pct": 0.70,"end_pct": 0.85,"profiles": ["binary_strong", "boundary_strong", "region_strong", "inter_soft"],"lr_mult": 0.55,"hard_topk_ratio": 0.15,"grad_clip": 0.80,"note": "Re-limpiar fondo y bordes después de aprender regiones.",},{"name": "curve_soft_finish","start_pct": 0.85,"end_pct": 1.01,"profiles": ["binary_soft", "boundary_soft", "inter_soft", "region_strong", "curve_soft"],"lr_mult": 0.35,"hard_topk_ratio": 0.10,"grad_clip": 0.70,"note": "Afinar curva y mantener regiones estables.",},]

print("============================================================")print("BLOQUE A LISTO — STAGES FLEXIBLES")print("============================================================")print("epochs:", CFG["epochs"])for s in CFG["stage_plan"]:print(f"{s['name']}: "f"{int(s['start_pct']*100)}% -> {int(s['end_pct']*100)}% | "f"profiles={s['profiles']} | note={s['note']}")
```

