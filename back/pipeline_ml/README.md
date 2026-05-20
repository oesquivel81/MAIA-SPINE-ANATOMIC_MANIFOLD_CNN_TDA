# pipeline_ml

Subpaquete inicial para construir el pipeline ML por etapas, con foco en debug temprano en Colab e instancia.

## Objetivo de esta primera version

- Tener un metodo principal unico para Colab con una sola entrada.
- Recibir una sola entrada tipo `dict` con:
  - `image`
  - `full_assets` (string concatenado con nombre completo + rutas de joblibs + rutas de recursos)
  - `request_id` (opcional)
- Separar el flujo en subpaquetes por etapa.
- Encender/apagar mensajes de debug y herramientas de avance.
- Encender/apagar redireccion de salidas: local, S3, Mongo, Kafka y Lambda.
- Mantener bitacora de avance para continuidad entre sesiones.
- Encadenar modelos de inferencia en este orden:
  - `cnn_curve`
  - `student_manifold_cnn`
  - `clustering`

## Estructura creada

```text
pipeline_ml/
  __init__.py
  config.py
  context.py
  logger.py
  entrypoint.py
  config.example.json
  models/
    cnn_curve.py
    student_manifold_cnn.py
    clustering.py
  stages/
    base.py
    ingestion.py
    preprocessing.py
    inference.py
    postprocessing.py
    persistence.py
  outputs/
    local.py
    s3.py
    mongo_metrics.py
    events.py
  normalization_stage/
    logger.py
    dynamic_engine.py
    traceability.py
```

## Normalization Stage (nuevo)

Se centralizo la logica de normalizacion agregada recientemente en:

- `pipeline_ml/normalization_stage/logger.py`
- `pipeline_ml/normalization_stage/dynamic_engine.py`
- `pipeline_ml/normalization_stage/traceability.py`

Objetivo:

- Mantener la logica de normalizacion agrupada en `pipeline_ml`.
- Unificar trazabilidad y logging de inicio de metodos.

## Metodo principal para Colab (una sola entrada)

```python
from pipeline_ml import run_pipeline_main

pipeline_input = {
  "image": my_image,
  "full_assets": "PACIENTE_APELLIDO_NOMBRE|C:/models/cnn_curve.joblib;C:/models/student_manifold_cnn.joblib;C:/models/clustering.joblib|C:/resources/r1.csv;C:/resources/r2.json",
  "request_id": "debug-colab-001",  # opcional
}

result = run_pipeline_main(
  pipeline_input=pipeline_input,
    config_file="./pipeline_ml/config.example.json",
)
```

## Metodo de compatibilidad (temporal)

Tambien existe `run_pipeline_entry(image, full_assets, config_file, request_id)` para no romper integraciones previas.

## Formato del string `full_assets`

`FULL_NAME|joblib1;joblib2|resource1;resource2`

- Segmento 1: nombre completo concatenado.
- Segmento 2: rutas de joblibs separadas por `;`.
- Segmento 3: rutas de recursos separadas por `;`.

## Banderas importantes

- `debug.enabled`: activa/desactiva logs.
- `debug.verbose`: activa mensajes de debug detallado.
- `debug.plots_show`: activa grids matplotlib en cada etapa (requiere `%matplotlib inline` en Colab).

---

## BinaryCurveStage — completado

Stage que conecta `PreprocessingStage` con el CNN `FastBinaryCurveUNet`.

### Entradas del payload

| Clave | Tipo | Descripcion |
|-------|------|-------------|
| `image` | `np.ndarray [H,W]` uint8 | Imagen normalizada de `PreprocessingStage` |

### Checkpoint

Se lee de `context.assets.joblib_paths[0]` (primer asset del string `full_assets`).  
Debe ser un archivo `.pt` o `.pth`. Validaciones aplicadas:

1. **Existencia** del archivo.
2. **Extension** `.pt/.pth` — si se pasa un `.joblib` se lanza `ValueError` con mensaje explicativo.
3. **LFS pointer** — si el archivo empieza con `version https://git-lfs...` se lanza `RuntimeError`.

```python
CNN_CURVE_PT = "/content/.../best_binary_curve_model.pt"
full_assets = f"PACIENTE|{CNN_CURVE_PT};{STUDENT_JOBLIB};{CLUSTER_JOBLIB}|{R1};{R2}"
```

### Salidas del payload

| Clave | Tipo | Descripcion |
|-------|------|-------------|
| `binary_mask` | `np.ndarray [H,W]` uint8 `{0,1}` | Mascara binaria CNN |
| `curve_mask` | `np.ndarray [H,W]` uint8 `{0,1}` | Mascara de curva CNN |
| `binary_mask_path` | str | PNG guardado en `outputs/cnn_curve/binary_mask.png` |
| `curve_mask_path` | str | PNG guardado en `outputs/cnn_curve/curve_mask.png` |
| `binary_curve_done` | bool `True` | Bandera para siguiente stage |

### Visualizacion (`plots_show=True`)

- `_show_image(image, title)` — imagen con shape/dtype/stats (mean, std, min, max, p5, p95).
- `_show_mask(mask, title, cmap)` — mascara con coverage%, pixel counts, valores unicos.
- `_compare_masks(image, binary_mask, curve_mask)` — grid 1×3 imagen | binaria | curva.

---

## CurveRefinementStage — completado

Stage de post-procesamiento: refina la curva espinal con programacion dinamica (DP) sobre un mapa de likelihood anatomica.

### Entradas del payload

| Clave | Tipo | Descripcion |
|-------|------|-------------|
| `image` | `np.ndarray [H,W]` | Imagen normalizada |
| `binary_mask` | `np.ndarray [H,W]` uint8 `{0,1}` | Mascara binaria de `BinaryCurveStage` |
| `curve_mask` | `np.ndarray [H,W]` uint8 `{0,1}` | Mascara de curva de `BinaryCurveStage` |

### Algoritmo

```
1. likelihood imagen  = CLAHE + Scharr gradient  (normalizado 0-1)
2. banda binaria      = dilate(binary_mask, kernel=45px)
3. bonus curva        = gaussian_filter(curve_mask, sigma=2)
4. likelihood_final   = 0.62*img + 0.18*banda + 0.20*bonus  (gaussian sigma=1.2)
5. curva inicial      = mediana por fila sobre binary_mask  (Gaussian smooth sigma=10)
6. curva DP           = DP vectorizado sobre offsets (-12..12) maximizando likelihood
                        con penalizacion de suavidad entre filas consecutivas
7. heatmap            = curva dibujada con thickness=6, blur_sigma=4  (threshold 0.25)
```

### Hiperparametros (constantes de modulo)

| Constante | Valor | Descripcion |
|-----------|-------|-------------|
| `_DP_SEARCH_RADIUS` | 110 | Ventana horizontal de busqueda por fila |
| `_DP_SMOOTH_LAMBDA` | 0.22 | Peso penalizacion suavidad |
| `_DP_PRIOR_LAMBDA` | 0.010 | Peso penalizacion desviacion de curva inicial |
| `_DP_BINARY_LAMBDA` | 0.08 | Peso bonus distancia a mascara binaria |
| `_DP_CENTER_LAMBDA` | 0.001 | Peso penalizacion desviacion del centro |
| `_DP_MAX_STEP` | 12 | Maximo salto en x entre filas consecutivas |
| `_HEATMAP_THRESHOLD` | 0.25 | Umbral para binarizar dp_heatmap en dp_mask |

### Salidas del payload

| Clave | Tipo | Descripcion |
|-------|------|-------------|
| `dp_ys` | `np.ndarray [N]` int32 | Coordenadas Y de la curva refinada |
| `dp_xs` | `np.ndarray [N]` float32 | Coordenadas X de la curva refinada |
| `dp_heatmap` | `np.ndarray [H,W]` float32 | Mapa de calor de la curva |
| `dp_mask` | `np.ndarray [H,W]` uint8 | Mascara binaria de la curva |
| `curve_csv_path` | str | CSV de puntos `(y, x)` |
| `curve_meta_path` | str | JSON de metadata e hiperparametros |
| `curve_refinement_done` | bool `True` | Bandera para siguiente stage |

### Archivos guardados en `outputs/curve_refinement/`

| Archivo | Descripcion |
|---------|-------------|
| `01_image_likelihood.png` | Mapa CLAHE+Scharr normalizado |
| `02_binary_band.png` | Banda dilatada de la mascara binaria |
| `03_curve_bonus.png` | Bonus de la curva suavizada |
| `04_likelihood_final.png` | Likelihood final combinada |
| `05_prior_curve.png` | Heatmap de la curva inicial |
| `06_curve_dp_heatmap.png` | Heatmap de la curva DP |
| `07_curve_dp_mask.png` | Mascara binaria de la curva DP |
| `curve_dp_heatmap.npy` | Heatmap float32 en formato NumPy |
| `curve_dp_mask.npy` | Mascara uint8 en formato NumPy |
| `curve_dp_centerline.csv` | Puntos de la curva: columnas `y`, `x` |
| `curve_refinement_metadata.json` | Hiperparametros, stats y rutas |

### Formato del CSV

```csv
y,x
25,166.0
26,166.0
27,165.999...
...
1006,115.07...
```

- **`y`** (int): fila del pixel (coordenada vertical, 0 = top).
- **`x`** (float): columna del pixel (coordenada horizontal, 0 = left).
- Una fila por cada fila de imagen donde existe curva.
- N ≈ H (height de la imagen), determinado por la extension vertical de la mascara binaria.

### Visualizacion (`plots_show=True`)

Se generan **tres figuras** en secuencia:

#### 1. `_show_refinement_grid` — grid 2×4  Pipeline completa de likelihood + curvas

| | Col 0 | Col 1 | Col 2 | Col 3 |
|---|---|---|---|---|
| **Fila 0** | Imagen normalizada | Binaria refinada | Likelihood imagen (CLAHE+Scharr) | Likelihood final (hot) |
| **Fila 1** | Curva previa (cyan) | Curva DP (lime) | Overlay heatmap+curva | Comparacion previa vs DP |

#### 2. `_show_curve_heatmap` — grid 2×3  Detalle del heatmap

| | Col 0 | Col 1 | Col 2 |
|---|---|---|---|
| **Fila 0** | Heatmap DP (hot) | Mascara DP binaria | Imagen + heatmap overlay |
| **Fila 1** | Curva previa (cyan) | Curva DP (lime) | Overlay completo (imagen+heatmap+curvas) |

#### 3. `_show_curve_csv` — grid 1×2  Contenido del CSV

- **Panel izquierdo**: scatter de la curva completa (x vs y, colormap viridis, eje Y invertido).
- **Panel derecho**: tabla matplotlib con `head(8) + ... + tail(8)` del CSV.
- Tambien imprime en stdout: `describe()`, `head(10)`, `tail(10)` del DataFrame.

## models/ — Clases identificadas del CNN binario/curva

> Fuente: `experiments/colab/PIPELINE_COMPLETE_2_CNN_OLD_SHARDS_REGIONIDX_FROM_YLABEL_FAST_20E_BS64 (8).ipynb`  
> Bloques 11, 12 y 13. Checkpoint: `experiments/pipeline_model/01_binary_curve_cnn/best_binary_curve_model.pt`

### `FastDoubleConv(nn.Module)`

Bloque convolucional doble, base del encoder y decoder.

```
Conv2d(in, out, 3, pad=1, bias=False) → BN → ReLU
Conv2d(out, out, 3, pad=1, bias=False) → BN → ReLU
```

### `FastBinaryCurveUNet(nn.Module)`

UNet simétrico de 3 niveles, 2 cabezas de salida (logits).  
Instanciación canónica: `FastBinaryCurveUNet(in_channels=1, base_ch=24)` → ~1.25M params.

**Encoder:**

| Bloque | Ch entrada → salida | Op               |
|--------|---------------------|------------------|
| e1     | 1 → 24              | FastDoubleConv   |
| e2     | 24 → 48             | MaxPool2d + FastDoubleConv |
| e3     | 48 → 96             | MaxPool2d + FastDoubleConv |
| b      | 96 → 192            | MaxPool2d + FastDoubleConv (bottleneck) |

**Decoder** (ConvTranspose2d + F.interpolate para size mismatch + skip concat):

| Bloque | Ch entrada → salida | Skip desde |
|--------|---------------------|------------|
| d3     | 192+96 → 96         | e3         |
| d2     | 96+48 → 48          | e2         |
| d1     | 48+24 → 24          | e1         |

**Cabezas de salida** (logits, aplicar `torch.sigmoid` para probabilidades):

| Cabeza        | Shape salida | Semántica                            |
|---------------|--------------|--------------------------------------|
| `head_binary` | [B,1,H,W]   | Máscara binaria de columna vertebral |
| `head_curve`  | [B,1,H,W]   | Línea media / curva de la columna    |

```python
out = model(x)   # x: [B,1,H,W] float [0,1]
# out["binary"] → logits   →  sigmoid >= 0.5  para máscara binaria
# out["curve"]  → logits   →  sigmoid >= 0.5  para máscara de curva
```

### `BinaryCurveRAMDataset(Dataset)` *(solo entrenamiento)*

```python
BinaryCurveRAMDataset(X, y_binary, y_curve, df_manifest)
# X:        [N,1,H,W] float32 normalizado [0,1]
# y_binary: [N,1,H,W] float32
# y_curve:  [N,1,H,W] float32
```

### Funciones de pérdida *(referencia, no se usan en inferencia)*

| Función | Descripción |
|---------|-------------|
| `dice_loss_logits(logits, target)` | Soft Dice desde logits |
| `soft_dice_score_logits(...)` | Dice score (métrica) |
| `curve_outside_binary_loss(curve_logits, y_binary)` | Penaliza curva fuera de la máscara binaria |
| `compute_binary_curve_loss(out, batch, weights)` | Suma ponderada total |

### Curriculum de entrenamiento (3 etapas)

| Etapa | Épocas | Foco |
|-------|--------|------|
| `binary_only_strong` | 1–25 | bce_bin=1.6, dice_bin=2.4 — binaria dominante |
| `binary_plus_curve` | 26–50 | balance binaria+curva |
| `curve_refine_inside_binary` | 51–90 | dice_curve=1.8, curve_outside=1.5 — curva fina |

### Formato del checkpoint

```python
ckpt = torch.load("best_binary_curve_model.pt", map_location="cpu")
# ckpt.keys() → "model_state_dict", "epoch", "stage", "best_val_loss"

model = FastBinaryCurveUNet(in_channels=1, base_ch=24)
model.load_state_dict(ckpt["model_state_dict"])
model.eval()
```

### Patrón de inferencia

```python
x = torch.from_numpy(image.astype("float32") / 255.0).unsqueeze(0).unsqueeze(0)  # [1,1,H,W]
with torch.no_grad():
    out = model(x)
binary_mask = (torch.sigmoid(out["binary"])[0, 0].numpy() >= 0.5).astype("uint8")
curve_mask  = (torch.sigmoid(out["curve"])[0, 0].numpy()  >= 0.5).astype("uint8")
```

---

## Pendiente — `BinaryCurveStage` ~~(`feature/cnn-binary-stage`)~~ ✅ completado

~~Stage del pipeline que conecta `PreprocessingStage` con el CNN.~~

Ver seccion **BinaryCurveStage — completado** arriba.

## Bitacora de avance

### 2026-05-19

- Se creo el paquete base `pipeline_ml` dentro de `back`.
- Se definio el contrato por etapas y 5 etapas iniciales.
- Se implemento el entrypoint unico `run_pipeline_entry`.
- Se agregaron banderas para debug y redireccion de salidas.
- Se dejaron stubs para S3/Mongo/Kafka/Lambda para conectar en siguientes iteraciones.
- Ajuste de arquitectura: la inferencia ahora modela explicitamente el pipeline `cnn_curve -> student_manifold_cnn -> clustering`.
- Se agrego `run_pipeline_main` para invocacion desde Colab con una sola entrada estructurada.

### 2026-05-20

- Implementado `BinaryCurveStage` en `feature/cnn-binary-stage` (mergeado a main via PR #12):
  - Arquitectura `FastBinaryCurveUNet` corregida (`.net` en lugar de `.block`, `u3/u2/u1` en lugar de `up3/up2/up1`).
  - Carga checkpoint `.pt` desde `assets.joblib_paths[0]`.
  - 3 validaciones en `loader.py`: existencia, extension `.pt/.pth`, LFS pointer.
  - Visualizacion: `_show_image`, `_show_mask`, `_compare_masks` (controladas por `plots_show`).
- Implementado `CurveRefinementStage` en `feature/curve-refinement-stage`:
  - DP vectorizado sobre offsets `-12..12` (~25x mas rapido que loop por columna).
  - Likelihood anatomica: `0.62*CLAHE_Scharr + 0.18*banda_binaria + 0.20*bonus_curva`.
  - Curva inicial via mediana de filas + Gaussian smooth.
  - 7 PNGs intermedios + heatmap `.npy` + `curve_dp_centerline.csv` + metadata JSON.
  - 3 visualizaciones: `_show_refinement_grid` (2x4), `_show_curve_heatmap` (2x3), `_show_curve_csv` (1x2 scatter+tabla).
- Agregado `debug.plots_show: bool` en `config.py` y propagado al contexto desde `entrypoint.py`.
- Orden de stages: `Ingestion → Preprocessing → BinaryCurve → CurveRefinement → Inference → Postprocessing → Persistence`.

## Siguientes pasos sugeridos

1. Conectar `outputs/s3.py` al cliente real de S3 del proyecto.
2. Conectar `outputs/mongo_metrics.py` al repositorio Mongo existente.
3. Implementar productor Kafka y dispatcher Lambda reales.
4. Implementar `InferenceStage` real con carga de joblibs para `student_manifold_cnn` y `clustering`.
5. Crear notebook de prueba en Colab para ejecutar todo el pipeline con imagen real y `plots_show=True`.
