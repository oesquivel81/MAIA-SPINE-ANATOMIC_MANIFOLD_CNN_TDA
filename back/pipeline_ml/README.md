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

---

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

## Pendiente — `BinaryCurveStage` (`feature/cnn-binary-stage`)

Stage del pipeline que conecta `PreprocessingStage` con el CNN.

- [ ] Instanciar `FastBinaryCurveUNet(in_channels=1, base_ch=24)` + cargar checkpoint
- [ ] Recibir `payload["image"]` normalizado de `PreprocessingStage`
- [ ] Normalizar a `[0,1]` float y reshape a `[1,1,H,W]`
- [ ] Inferir con `torch.no_grad()` en CPU o CUDA según disponibilidad
- [ ] Guardar `binary_mask.png` y `curve_mask.png` en `outputs_dir`
- [ ] Actualizar payload: `binary_mask`, `curve_mask`, `binary_mask_path`, `curve_mask_path`
- [ ] Agregar `paths.binary_curve_model_path` a `PipelinePaths` en `config.py`
- [ ] Agregar visualización con `plots_show` (equivalente a `_compare_images` de preprocessing)
- `routing.colab_mode`: modo Colab.
- `routing.instance_mode`: modo instancia.
- `routing.write_outputs_to_s3`: enviar salidas a S3.
- `routing.write_metrics_to_mongo`: guardar metricas historicas en Mongo.
- `routing.publish_events_to_kafka`: publicar progreso a Kafka.
- `routing.invoke_lambda_for_metrics`: invocar Lambda para procesamiento de metricas/eventos.

## Bitacora de avance

### 2026-05-19

- Se creo el paquete base `pipeline_ml` dentro de `back`.
- Se definio el contrato por etapas y 5 etapas iniciales.
- Se implemento el entrypoint unico `run_pipeline_entry`.
- Se agregaron banderas para debug y redireccion de salidas.
- Se dejaron stubs para S3/Mongo/Kafka/Lambda para conectar en siguientes iteraciones.
- Ajuste de arquitectura: la inferencia ahora modela explicitamente el pipeline `cnn_curve -> student_manifold_cnn -> clustering`.
- Se agrego `run_pipeline_main` para invocacion desde Colab con una sola entrada estructurada.

## Siguientes pasos sugeridos

1. Conectar `outputs/s3.py` al cliente real de S3 del proyecto.
2. Conectar `outputs/mongo_metrics.py` al repositorio Mongo existente.
3. Implementar productor Kafka y dispatcher Lambda reales.
4. Añadir carga real de joblibs y ejecucion de inferencia.
5. Crear notebook de prueba en Colab para ejecutar `run_pipeline_entry` con casos de error.
