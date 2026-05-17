# v.02.A — first_cnn_generator_channel_to_2cnn_combined_v7_fullres

## Experiment ID

```text
v02A_first_cnn_generator_channel_to_2cnn_combined_v7_fullres_20260517_224251
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