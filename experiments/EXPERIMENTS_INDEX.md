# MAIA Spine Experiments Index

## v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

- Experiment ID: `v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_035024`
- Version slug: `v02A`
- Repo path: `experiments/v02A`
- Drive backup: `/content/drive/MyDrive/TDA_PIPELINE/EXPERIMENT_BACKUPS/MAIA_SPINE/v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_035024`
- Branch: `experiment/v02A`

### Restore

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

---

<!-- v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_035024 — curve+kfold -->

## v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

- Experiment ID: `v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_035024`
- Version slug: `v02A`
- Repo path: `experiments/v02A`
- Branch: `experiment/v02A`

### Added analysis

- Curve analysis: `artifacts/curve_analysis/`
- KFold: `artifacts/kfold/`
- Curve report: `artifacts/curve_analysis/CURVE_ANALYSIS_REPORT.md`
- KFold report: `artifacts/kfold/KFOLD_REPORT.md`

---

## v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

- Experiment ID: `v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_164013`
- Version slug: `v02A`
- Repo path: `experiments/v02A`
- Drive backup: `/content/drive/MyDrive/TDA_PIPELINE/EXPERIMENT_BACKUPS/MAIA_SPINE/v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_164013`
- Branch: `experiment/v02A`

### Restore

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

---

<!-- v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_164013 — curve+kfold -->

## v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

- Experiment ID: `v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_164013`
- Version slug: `v02A`
- Repo path: `experiments/v02A`
- Branch: `experiment/v02A`

### Added analysis

- Curve analysis: `artifacts/curve_analysis/`
- KFold: `artifacts/kfold/`
- Curve report: `artifacts/curve_analysis/CURVE_ANALYSIS_REPORT.md`
- KFold report: `artifacts/kfold/KFOLD_REPORT.md`

---

## v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

- Experiment ID: `v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_212428`
- Version slug: `v02A`
- Repo path: `experiments/v02A`
- Drive backup: `/content/drive/MyDrive/TDA_PIPELINE/EXPERIMENT_BACKUPS/MAIA_SPINE/v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_212428`
- Branch: `experiment/v02A`

### Restore

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

---
