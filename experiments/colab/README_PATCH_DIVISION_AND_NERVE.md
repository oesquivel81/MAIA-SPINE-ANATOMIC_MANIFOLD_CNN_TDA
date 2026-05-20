# README — División de Parches e Imagen del Nervio (Curva Espinal)

> **Notebook fuente:**  
> `PIPELINE_COMPLETE_2_CNN_OLD_SHARDS_REGIONIDX_FROM_YLABEL_FAST_20E_BS64 (8).ipynb`  
> Ubicación: `experiments/colab/`  
> Total de celdas: 255

---

## Contexto General

El cuaderno implementa el **segundo CNN de la pipeline MAIA-SPINE**. Recibe como entrada los
"shards viejos" (`PATCH_SHARDS_INTERVERTEBRAL_GEOMETRY_SIGNALS`) que fueron pre-construidos
en una pipeline anterior que extrajo parches centrados en la curva espinal de la imagen
normalizada por paciente. El notebook:

1. **Carga y audita** los shards pre-construidos.
2. **Construye targets de supervisión** (binario, multiclase, boundary, intervertebral, ordinal)
   a partir del par `(y_label, region_idx)`.
3. **Entrena** un modelo multi-head con esos targets.
4. **Reconstruye** predicciones por paciente pegando los parches sobre la imagen global
   normalizada.
5. **Genera nuevos shards de proyecciones estructurales** para la siguiente etapa (TDA).

---

## 1. División de la Imagen Normalizada en Parches

### 1.1 Origen de los parches (shards "viejos")

Los parches NO se extraen dentro de este notebook. Se consumen desde archivos NPZ
pre-construidos almacenados en Google Drive:

```
/content/drive/MyDrive/TDA_PIPELINE/
  GRAY_TO_EXTRACTOR_CURVE_robust_mad/
    PATCH_SHARDS_INTERVERTEBRAL_GEOMETRY_SIGNALS/
      shards_npz/      ← archivos shard_*.npz
      csv/
      config/
```

El metadato que guía **cómo se cortaron** los parches de la imagen normalizada
proviene del archivo:

```
curve_centered_patch_metadata.csv
```

que se copia por paciente a:

```
/content/patient_spatial_csvs/<PATIENT>/
  curve_centered_patches__curve_centered_patch_metadata.csv
  curve_metadata.csv
  normalized_full_image.png   ← imagen radiográfica normalizada completa
  binary_mask_normalized.png
  multiclass_color_mask_normalized.png
  normalization_info.json
```

### 1.2 Estructura del shard NPZ (evidencia: BLOQUE OLD-2, celda 3)

Cada archivo `.npz` contiene:

| Clave | Shape | dtype | Descripción |
|---|---|---|---|
| `X` | `[N, 192, 128, 10]` | `uint8` | N parches de 192 × 128 px con 10 canales (NHWC) |
| `y_label` | `[N, 192, 128]` | `uint8` | Máscara foreground por píxel (gris o binaria) |
| `region_idx` | `[N]` | escalar | Índice anatómico (1–24) de la región del parche |
| `patient_key` | `[N]` | str | ID del paciente (e.g. `N_1`) |
| `patch_id` | `[N]` | str | Nombre único del parche (e.g. `N_1_patch_0002`) |
| `channel_names` | `[10]` | object | Nombres de los 10 canales |

```python
# BLOQUE OLD-0 — constantes de tamaño de parche
PATCH_H = 192
PATCH_W = 128
N_INPUT_CHANNELS = 10
NUM_CLASSES = 25  # 24 regiones + background

# Índices de canales de interés
BAND_CH_IDX         = 1   # máscara de banda espinal
BALANCED_EDGE_CH_IDX = 2  # bordes balanceados
ORIENTED_EDGE_CH_IDX = 3  # bordes orientados
T_MAP_CH_IDX        = 5   # mapa T (temperature/gradient)
```

### 1.3 Nombres de los 10 canales originales (evidencia: output BLOQUE OLD-2)

```
Keys: ['X', 'y_label', 'patient_key', 'patch_id', 'region_idx', 'channel_names']
channel_names (10,) object
```

Los canales 0–9 proceden del extractor de curvas (`GRAY_TO_EXTRACTOR_CURVE_robust_mad`):
incluyen la imagen gris normalizada (CH0), la banda espinal (CH1), bordes balanceados
(CH2), bordes orientados (CH3), mapa-T (CH5) y otros mapas geométricos auxiliares.

### 1.4 Carga de shards a RAM y conversión NHWC→NCHW (evidencia: BLOQUE OLD-4, celda 5)

```python
for shard_path in tqdm(old_shard_files, desc="Load old shards to RAM"):
    d = np.load(shard_path, allow_pickle=True)

    X        = d["X"]         # [N, H, W, C]  uint8
    y_label  = d["y_label"]   # [N, H, W]      uint8
    region_idx = d["region_idx"]

    # NHWC uint8 → NCHW float32 0..1
    X_chw = np.transpose(X, (0, 3, 1, 2)).astype(np.float32) / 255.0
```

---

## 2. Creación del Nervio / Máscara Espinal

El término "nervio" corresponde en el cuaderno a la **curva espinal** (eje de la columna
vertebral / ligamento intervertebral) capturada en la máscara `y_label` y organizada
en 24 regiones anatómicas a través de `region_idx`.

### 2.1 `make_multiclass_from_y_label_region` (evidencia: BLOQUE OLD-3, celda 4)

Esta es la función principal que construye la máscara de nervio por píxel:

```python
def make_multiclass_from_y_label_region(y_label, region_idx, threshold=3):
    """
    y_label puede ser:
    - binaria 0/255
    - gris con foreground > threshold

    region_idx define la clase anatómica de ese parche.
    """
    y_label   = np.asarray(y_label)
    region_idx = int(region_idx)

    y_multi = np.zeros_like(y_label, dtype=np.int64)

    if region_idx < 1 or region_idx > 24:
        return y_multi          # fuera de rango → todo background

    fg = y_label > threshold    # umbral = 3 en escala uint8
    y_multi[fg] = region_idx    # pinta los píxeles de foreground con la clase anatómica

    return y_multi
```

**Semántica:** cada parche tiene un `region_idx` ∈ [1, 24] que identifica cuál de los 24
espacios intervertebrales contiene. La máscara `y_label` marca qué píxeles del parche
pertenecen al ligamento/disco intervertebral. `make_multiclass_from_y_label_region` los
funde en una única máscara de clase `y_multi`.

### 2.2 `boundary_from_label_np` — bordes del nervio (evidencia: BLOQUE OLD-3, celda 4)

```python
def boundary_from_label_np(mask):
    mask = np.asarray(mask).astype(np.int32)
    bd   = np.zeros_like(mask, dtype=np.float32)

    # Bordes horizontales
    bd[:, 1:]  = np.maximum(bd[:, 1:],  (mask[:, 1:]  != mask[:, :-1]).astype(np.float32))
    bd[:, :-1] = np.maximum(bd[:, :-1], (mask[:, 1:]  != mask[:, :-1]).astype(np.float32))

    # Bordes verticales
    bd[1:, :]  = np.maximum(bd[1:, :],  (mask[1:, :] != mask[:-1, :]).astype(np.float32))
    bd[:-1, :] = np.maximum(bd[:-1, :], (mask[1:, :] != mask[:-1, :]).astype(np.float32))

    bd[mask == 0] = 0.0   # solo foreground
    return bd
```

### 2.3 `make_intervertebral_target_from_channels` — señal intervertebral (evidencia: BLOQUE OLD-3, celda 4)

```python
def make_intervertebral_target_from_channels(x_chw, y_boundary):
    """
    Canal intervertebral sintético:
    - 70 % oriented_edge (CH3) × band_mask (CH1)
    - 30 % boundary target
    """
    band     = x_chw[BAND_CH_IDX]         # CH1
    oriented = x_chw[ORIENTED_EDGE_CH_IDX] # CH3

    band01     = normalize_01_np(band)
    oriented01 = normalize_01_np(oriented)

    inter = 0.70 * oriented01 * (band01 > 0.05).astype(np.float32)
    inter = np.maximum(inter, 0.30 * y_boundary)

    return np.clip(inter, 0.0, 1.0).astype(np.float32)
```

### 2.4 `make_ordinal_from_region_and_mask` — etiqueta ordinal (evidencia: BLOQUE OLD-3, celda 4)

```python
def make_ordinal_from_region_and_mask(y_multi):
    """
    Etiqueta ordinal: clase/24 dentro del foreground.
    Encodes el orden craneocaudal de la región.
    """
    y_ord = y_multi.astype(np.float32) / 24.0
    y_ord[y_multi <= 0] = 0.0
    return y_ord.astype(np.float32)
```

### 2.5 Pipeline completa de construcción de targets (evidencia: BLOQUE OLD-4, celda 5)

```python
for i in range(n):
    y_multi    = make_multiclass_from_y_label_region(
                     y_label=y_label[i],
                     region_idx=int(region_idx[i]),
                     threshold=3)

    y_binary   = (y_multi > 0).astype(np.float32)
    y_boundary = boundary_from_label_np(y_multi)
    y_inter    = make_intervertebral_target_from_channels(
                     x_chw=X_chw[i], y_boundary=y_boundary)
    y_ordinal  = make_ordinal_from_region_and_mask(y_multi)
```

---

## 3. Rutas Espaciales de los Parches (CSV de Metadatos)

El archivo `curve_centered_patch_metadata.csv` contiene las coordenadas de cada parche
dentro de la imagen normalizada global. Se usa en el **reconstructor** (celda 24):

```python
# Columnas buscadas en curve_centered_patch_metadata.csv
coord_sets = [
    ("x1", "y1", "x2", "y2"),                             # bbox del parche
    ("clamped_x1", "clamped_y1", "clamped_x2", "clamped_y2"),
    ("requested_x1", "requested_y1", "requested_x2", "requested_y2"),
]

# Columnas de identificación
# patient_key  : ID paciente
# patch_id     : ID único del parche
# region_idx   : índice de región (1-based)
# center_x/y   : centroide del parche
```

**Nombre nominal por parche:** `REGION_{region_idx:02d}`  
**Ejemplo del manifest** (salida BLOQUE OLD-4):

```
idx  patient_key  sample_id       pair_name   region_idx
0    N_1          N_1_patch_0000  REGION_00   0
1    N_1          N_1_patch_0001  REGION_01   1
2    N_1          N_1_patch_0002  REGION_02   2
3    N_1          N_1_patch_0003  REGION_03   3
4    N_1          N_1_patch_0004  REGION_04   4
```

---

## 4. Reconstrucción Global (Nervio sobre Imagen Completa)

### 4.1 `find_normalized_full_image` (evidencia: celda 24)

```python
def find_normalized_full_image(patient_key):
    """Busca la imagen normalizada global del paciente."""
    candidates = [
        os.path.join(CURVE_ROOT_LOCAL, patient_key,
                     "curve_centered_patches", "normalized_full_image.png"),
        os.path.join(CURVE_ROOT_LOCAL, patient_key,
                     "normalized_full_image.png"),
        os.path.join(CURVE_ROOT_DRIVE, patient_key,
                     "curve_centered_patches", "normalized_full_image.png"),
        os.path.join(CURVE_ROOT_DRIVE, patient_key,
                     "normalized_full_image.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None
```

### 4.2 `predict_patch` (evidencia: celda 24)

```python
@torch.no_grad()
def predict_patch(model, ds, ds_idx):
    """Infiere todas las cabezas sobre un único parche del dataset."""
    sample = ds[int(ds_idx)]
    batch  = move_batch_to_device({k: v.unsqueeze(0) if torch.is_tensor(v) else v
                                    for k, v in sample.items()})
    model.eval()

    with torch.cuda.amp.autocast(enabled=USE_AMP):
        out = model(batch["x"])

    return {
        "base":       sample["x"][0].cpu().numpy(),         # CH0 normalizado
        "pred_mc":    torch.argmax(out["multiclass"], 1)[0].cpu().numpy(),
        "pred_bin":   torch.sigmoid(out["binary"])[0,0].cpu().numpy(),
        "pred_bd":    torch.sigmoid(out["boundary"])[0,0].cpu().numpy(),
        "pred_inter": torch.sigmoid(out["intervertebral"])[0,0].cpu().numpy(),
        "pred_ord":   torch.sigmoid(out["ordinal"])[0,0].cpu().numpy(),
    }
```

---

## 5. Generación de Shards Estructurales (salida hacia TDA)

### 5.1 BLOQUE 1 — `load_patient_projection_tensor` (evidencia: celda 32)

Tras reconstruir cada paciente, se construye un tensor de proyecciones estructurales
de 5 canales para la siguiente etapa (TDA / manifold):

```python
CHANNELS = [
    ("baseline",      "normalized_full_image_used.png"),  # CH0 imagen gris
    ("binary",        "pred_binary_confidence.png"),       # CH1 confianza binaria
    ("boundary",      "pred_boundary.png"),                # CH2 bordes
    ("intervertebral","pred_intervertebral.png"),          # CH3 espacios intervert.
    ("ordinal",       "pred_ordinal.png"),                 # CH4 posición ordinal
]

TARGET_H = 512
TARGET_W = 256
SHARD_SIZE = 64  # pacientes por shard

def load_patient_projection_tensor(patient_key):
    """
    Devuelve X: [C=5, H=512, W=256] float32
    Cada canal se redimensiona con resize_keep_aspect_pad_gray()
    para mantener proporción y centrar en canvas negro.
    """
    channel_arrays = []
    for ch_name, fname in CHANNELS:
        img = read_gray_01(os.path.join(PATIENTS_DIR, patient_key, fname))
        img = resize_keep_aspect_pad_gray(img, out_h=TARGET_H, out_w=TARGET_W)
        channel_arrays.append(img)

    X = np.stack(channel_arrays, axis=0)  # [5, 512, 256]
    return X, ...
```

### 5.2 Shard de salida NPZ estructural

```python
np.savez_compressed(
    shard_path,
    X             = X_shard.astype(np.float32),  # [N, 5, 512, 256]
    patient_key   = patient_keys,
    channel_names = np.array(CHANNEL_NAMES, dtype=object),
    status        = status_array,
    pred_regions  = pred_regions_array,
    n_pred_regions= n_pred_regions_array,
)
```

---

## 6. Diagrama de Flujo Resumido

```
Imagen radiográfica normalizada (normalized_full_image.png)
        │
        ▼
curve_centered_patch_metadata.csv
(x1,y1,x2,y2 por parche)
        │
        ▼
Parches PATCH_H=192 × PATCH_W=128, 10 canales
  X: [N,192,128,10] uint8
  y_label: [N,192,128] uint8   ← máscara del "nervio" / curva espinal
  region_idx: escalar 1..24    ← región anatómica del parche
        │
        ▼
make_multiclass_from_y_label_region(y_label, region_idx, threshold=3)
  ──> y_multiclass: píxeles foreground etiquetados con clase 1..24
        │
  ┌─────┴──────────────────────────────┐
  ▼                                    ▼
y_binary = (y_multi > 0)        y_boundary = boundary_from_label_np(y_multi)
  ▼                                    ▼
  └─────────────────── y_intervertebral = make_intervertebral_target_from_channels(...)
                                        y_ordinal = make_ordinal_from_region_and_mask(...)
        │
        ▼
OldPatchDatasetRAM → DataLoader (batch=64)
        │
        ▼
FastMultiHeadModel (10→binary/boundary/inter/ordinal/multiclass)
        │
        ▼
predict_patch() × todos los parches del paciente
        │
        ▼
reconstruct_patient_from_patches()  ← pega predicciones sobre imagen global
        │
        ▼
load_patient_projection_tensor()    ← 5 canales [C,512,256]
        │
        ▼
Shards NPZ estructurales → siguiente etapa (TDA / manifold)
```

---

## 7. Archivos Relacionados en el Repositorio

| Archivo | Rol |
|---|---|
| `back/pipeline_ml/stages/binary_curve.py` | Inicia la inferencia CNN en la pipeline de producción |
| `back/pipeline_ml/stages/curve_refinement.py` | Refinamiento DP de la curva espinal detectada |
| `back/pipeline_ml/cnn_curve/architecture.py` | `FastBinaryCurveUNet` — arquitectura del modelo |
| `back/pipeline_ml/cnn_curve/loader.py` | Carga del checkpoint `.pt` con validaciones |
| `back/pipeline_ml/README.md` | Documentación de la pipeline de producción |

---

*Generado a partir del análisis del notebook `PIPELINE_COMPLETE_2_CNN_OLD_SHARDS_REGIONIDX_FROM_YLABEL_FAST_20E_BS64 (8).ipynb` — 2025-05-20*
