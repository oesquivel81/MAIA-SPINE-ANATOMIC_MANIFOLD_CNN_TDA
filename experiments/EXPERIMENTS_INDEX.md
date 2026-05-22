# MAIA Spine Experiments Index

---

## Session log — 2026-05-21 | Rama: `chore/eks-deploy-requirements-update`

### Git: Merges de feature branches completados

| Rama | Estado | Detalle |
|---|---|---|
| `feature/cnn-binary-stage` | ✅ Ya integrada | Estaba en el historial de `chore` (PR #12) |
| `feature/curve-refinement-stage` | ✅ Ya integrada | (PR #13) |
| `feature/curve-patch-stage` | ✅ Ya integrada | (PR #14) |
| `feature/student-patch-stage` | ✅ Ya integrada | (PR #15) |
| `feature/patch-reconstruction-stage` | ✅ Mergeada en esta sesión | Conflicto "add/add" en `patch_reconstruction.py` — resuelto conservando `combined_signal_path` y `analysis_grid_path` en payload (versión HEAD más nueva) |

- **Merge commit**: `12dd7765d` — "Merge branch 'feature/patch-reconstruction-stage' into chore/eks-deploy-requirements-update"
- **Pushed**: `a52ce409f..12dd7765d` → origin/chore/eks-deploy-requirements-update ✅

### Auditoría de stubs/modelos hardcodeados

- `back/pipeline_ml/models/cnn_curve.py` → `CnnCurveModel`: **stub/dead code** — no es usado por ningún stage
- `back/pipeline_ml/models/student_manifold_cnn.py` → `StudentManifoldCnnModel`: **stub/dead code**
- `back/pipeline_ml/models/clustering.py` → `ClusteringModel`: **stub/dead code**
- `back/pipeline_ml/stages/postprocessing.py`: trivial stub (solo `payload["postprocessed"] = True`)
- Inferencia real: `InferenceStage` usa GMM desde `joblib_paths[2]`; `BinaryCurveStage` usa `FastBinaryCurveUNet` (.pt checkpoint)

---

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

## v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

- Experiment ID: `v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260518_040947`
- Version slug: `v02A`
- Repo path: `experiments/v02A`
- Drive backup: `/content/drive/MyDrive/TDA_PIPELINE/EXPERIMENT_BACKUPS/MAIA_SPINE/v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260518_040947`
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

## v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

- Experiment ID: `v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260518_050108`
- Version slug: `v02A`
- Repo path: `experiments/v02A`
- Drive backup: `/content/drive/MyDrive/TDA_PIPELINE/EXPERIMENT_BACKUPS/MAIA_SPINE/v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260518_050108`
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

## v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

- Experiment ID: `v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260518_050628`
- Version slug: `v02A`
- Repo path: `experiments/v02A`
- Drive backup: `/content/drive/MyDrive/TDA_PIPELINE/EXPERIMENT_BACKUPS/MAIA_SPINE/v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260518_050628`
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

## v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

- Experiment ID: `v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260518_054501`
- Version slug: `v02A`
- Repo path: `experiments/v02A`
- Drive backup: `/content/drive/MyDrive/TDA_PIPELINE/EXPERIMENT_BACKUPS/MAIA_SPINE/v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260518_054501`
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
