# MAIA-SPINE — Anatomic Manifold CNN + TDA

Sistema de análisis clínico automático de escoliosis a partir de radiografías de columna vertebral.  
Combina CNN binaria de curva, red student multihead (4 cabezas), reconstrucción de parches y análisis probabilístico GMM con TDA.

---

## Índice

1. [Arquitectura general](#arquitectura-general)
2. [Pipeline ML — etapas](#pipeline-ml--etapas)
3. [Modelos](#modelos)
4. [Cómo invocar el pipeline](#cómo-invocar-el-pipeline)
5. [Formato de assets](#formato-de-assets)
6. [Configuración JSON](#configuración-json)
7. [Respuesta del pipeline](#respuesta-del-pipeline)
8. [DTO FastAPI](#dto-fastapi)
9. [Estructura del proyecto](#estructura-del-proyecto)
10. [Ejecución local (Docker)](#ejecución-local-docker)

---

## Arquitectura general

```
Radiografía (JPG/PNG)
        │
        ▼
┌───────────────────────────────────────────────────────┐
│                   PipelineML                          │
│                                                       │
│  Ingestion → Preprocessing → BinaryCurve             │
│      → CurveRefinement → CurvePatch                   │
│      → StudentPatch → PatchReconstruction             │
│      → Inference (GMM) → Postprocessing               │
│      → Persistence                                    │
└───────────────────────────────────────────────────────┘
        │
        ▼
 PipelineResult  →  FastAPI endpoint  →  JSON clínico
```

Cada etapa recibe y devuelve un `payload: dict`. El contexto (`PipelineContext`) transporta rutas, assets y metadata sin pasar por el payload.

---

## Pipeline ML — etapas

| # | Nombre | Clase | Entrada clave | Salida clave |
|---|--------|-------|---------------|--------------|
| 1 | **Ingestion** | `IngestionStage` | `image` (ndarray) | `ingested=True` |
| 2 | **Preprocessing** | `PreprocessingStage` | `image` | `image` normalizada 1024×W, `normalized_image_path` |
| 3 | **BinaryCurve** | `BinaryCurveStage` | `image` (1024×W) | `binary_mask`, `curve_mask`, `binary_mask_path`, `curve_mask_path` |
| 4 | **CurveRefinement** | `CurveRefinementStage` | `binary_mask` | `dp_ys`, `dp_xs`, `dp_heatmap`, `curve_csv_path` |
| 5 | **CurvePatch** | `CurvePatchStage` | `dp_ys/dp_xs` | `patches` (8), `patch_meta`, `patch_csv_path` |
| 6 | **StudentPatch** | `StudentPatchStage` | `patches` | `student_outputs` (probs 4 cabezas), `patch_input_paths` |
| 7 | **PatchReconstruction** | `PatchReconstructionStage` | `student_outputs` | `recon_maps`, `combined_signal`, `gap_analysis`, `spatial_index` |
| 8 | **Inference** | `InferenceStage` | `gap_analysis`, `spatial_index` | `inference` (GMM), `cobb_angle_deg` |
| 9 | **Postprocessing** | `PostprocessingStage` | todo el payload | agregaciones finales |
| 10 | **Persistence** | `PersistenceStage` | payload completo | escritura S3/Mongo/local |

### Detalle por etapa relevante

#### 2. Preprocessing
- Carga 249 perfiles de normalización desde `normalization_profile_index.jsonl`.
- Selecciona el perfil más cercano al histograma de entrada (distancia coseno).
- Aplica equalización adaptativa (CLAHE + stretch lineal) + resize a 1024 px de altura.
- Guarda `normalized_image.png` y `normalization_trace.json`.

#### 3. BinaryCurve
- Carga checkpoint PyTorch (`.pt`) de la CNN binaria.
- Produce `binary_mask` (región espinal) y `curve_mask` (centerline).
- Guarda `binary_mask.png` y `curve_mask.png`.

#### 4. CurveRefinement
- Programación dinámica (DP) sobre el likelihood de la curva.
- Produce 982 puntos `(y, x)` de la centerline suavizada.
- Guarda `curve_dp_centerline.csv`.

#### 5. CurvePatch
- Divide la curva en 8 parches verticales solapados.
- Cada parche = ventana de imagen normalizada centrada en la curva.

#### 6. StudentPatch
- Red StudentUNet1CH4Heads (4 cabezas sigmoid [0,1]):
  - `binary` — región vertebral
  - `boundary` — bordes
  - `intervertebral` — espacio intervertebral
  - `ordinal` — señal ordinal de posición
- Por cada parche guarda `patch_XX/input.png` + PNG por cabeza.
- `patch_input_paths` = lista de todos los `input.png`.

#### 7. PatchReconstruction
- Reconstruye mapas H×W ponderando 8 parches con frecuencia de cobertura.
- Genera `combined_signal` = señal combinada (A∩B) \ cuerpos vertebrales.
- Análisis de peaks/gaps sobre perfil vertical (`df_events`, `df_profile`).
- Índice espacial: centroides de vértebras + peaks sobre la curva DP.
- Guarda:
  - `combined_signal.png` — señal de gaps/bordes sobre fondo blanco
  - `analysis_grid.png` — grid de los 4 mapas reconstruidos
  - `vertical_profiles.png`
  - `gap_peak_analysis/patient_gap_peak_analysis.png`
  - `spatial_index/panel_spatial_index_curve_centroids_peaks.png`
  - `combined_signal_stats.csv`, `vertebra_gap_peak_analysis.csv`

#### 8. Inference (GMM clínico-probabilístico)
- Carga bundle joblib con: `feature_cols`, `best_model` (GMM), `best_transform`, `fitted_transforms`, `best_representation`.
- Construye 20 features por región gap_peak:
  - `cobb_angle_deg`, distancias al ápex, arc_length, wavelength_prev/next, gap_strength_mean, peak_height, n_peaks, etc.
- Transforma con RobustScaler + KernelPCA (poly).
- Predice cluster GMM + probabilidades + entropía.
- Estima ángulo de Cobb (diferencia upper/lower 1/3 de ángulos locales).
- Guarda:
  - `{patient_key}_clinical_payload.json`
  - `clinical_summary.csv`, `clinical_regions.csv`
  - `cluster_predictions.csv`, `cluster_summary.csv`, `X_raw_features.csv`
  - `clinical_probabilistic_plot.png` (si `plots_show=True`)

---

## Modelos

| Slot | Modelo | Formato | Descripción |
|------|--------|---------|-------------|
| `joblib_paths[0]` | CNN Curva Binaria | `.pt` (PyTorch) | Segmentación espinal + curva centerline |
| `joblib_paths[1]` | StudentUNet1CH4Heads | `.pt` (PyTorch) | 4 cabezas: binary, boundary, intervertebral, ordinal |
| `joblib_paths[2]` | Bundle GMM clustering | `.joblib` (sklearn) | GMM probabilístico + transforms RobustScaler/KernelPCA |

---

## Cómo invocar el pipeline

### Desde Colab / Python directo

```python
import sys
sys.path.insert(0, "/content/MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA/back")

from pipeline_ml.entrypoint import run_pipeline_main
import cv2

# 1. Cargar imagen
image = cv2.imread("/path/to/S_26.jpg", cv2.IMREAD_GRAYSCALE)

# 2. Construir assets string:  NOMBRE|joblib0;joblib1;joblib2|recurso1;recurso2
FULL_ASSETS = (
    "APELLIDO_NOMBRE"
    "|/path/cnn_curve.pt;/path/student.pt;/path/clustering.joblib"
    "|/path/r1.csv;/path/r2.json"
)

# 3. Ejecutar
result = run_pipeline_main(
    pipeline_input={
        "image":       image,
        "full_assets": FULL_ASSETS,
        "request_id":  "debug-001",   # opcional
    },
    config_file="/path/config.colab.debug.json",
)

# 4. Acceder al JSON clínico consolidado
clinical = result["outputs"]["clinical_result"]
print(clinical["predictions"]["cobb_angle_deg"])
print(clinical["images"]["combined_signal"])
print(clinical["images"]["patch_inputs"])   # lista de 8 rutas
```

### Desde FastAPI

```python
from app.schemas.pipeline_schema import PipelineClinicalResultDTO

@router.post("/analyze", response_model=PipelineClinicalResultDTO)
async def analyze(file: UploadFile = File(...), ...):
    image = decode_image(await file.read())
    outputs = run_pipeline_main({"image": image, "full_assets": assets_str})
    return PipelineClinicalResultDTO.from_pipeline_output(outputs["outputs"])
```

---

## Formato de assets

```
FULL_NAME|joblib_path_0;joblib_path_1;joblib_path_2|resource_path_0;resource_path_1
```

| Parte | Contenido |
|-------|-----------|
| `FULL_NAME` | Nombre completo del paciente |
| `joblib_paths` | Separados por `;` — CNN curva, Student, Bundle GMM |
| `resource_paths` | Separados por `;` — recursos auxiliares opcionales |

---

## Configuración JSON

```json
{
  "debug": {
    "enabled": true,
    "verbose": true,
    "print_step_summary": true,
    "save_debug_artifacts": false,
    "plots_show": false
  },
  "routing": {
    "colab_mode": true,
    "instance_mode": false,
    "write_local_artifacts": true,
    "write_outputs_to_s3": false,
    "write_metrics_to_mongo": false,
    "publish_events_to_kafka": false,
    "invoke_lambda_for_metrics": false
  },
  "paths": {
    "local_artifacts_dir": "./pipeline_ml_artifacts",
    "normalization_profile_jsonl": "",
    "workspace_root": "./",
    "n_curve_patches": 8
  }
}
```

`plots_show: true` → muestra figuras matplotlib inline (Colab/Jupyter).  
`plots_show: false` → solo guarda archivos en disco (producción).

---

## Respuesta del pipeline

`run_pipeline_main` devuelve un `dict` con esta estructura:

```
{
  "request_id":            str,
  "ok":                    bool,
  "message":               str,
  "outputs": {
    "request_id":          str,
    "full_name":           str,
    "joblib_paths":        [str, ...],
    "resource_paths":      [str, ...],
    "payload":             { ... },           ← payload completo interno
    "clinical_result":     { ... },           ← JSON clínico consolidado ✓
    "clinical_result_path": str,              ← ruta al archivo .json guardado
    "s3":                  dict | None,
    "mongo":               dict | None,
  },
  "metrics": {
    "request_id":          str,
    "total_ms":            float,
    "step_durations_ms":   { "ingestion": ms, "preprocessing": ms, ... },
    "progress_messages":   ["ingestion:ok:10ms", ...]
  }
}
```

### `clinical_result` — JSON clínico consolidado

Guardado en `outputs/{request_id}/outputs/clinical_result.json`:

```json
{
  "request_id": "debug-001",
  "patient_name": "APELLIDO_NOMBRE",

  "images": {
    "normalized_image":    "outputs/.../normalized_image.png",
    "binary_mask":         "outputs/.../cnn_curve/binary_mask.png",
    "curve_mask":          "outputs/.../cnn_curve/curve_mask.png",
    "combined_signal":     "outputs/.../patch_reconstruction/combined_signal.png",
    "analysis_grid":       "outputs/.../patch_reconstruction/analysis_grid.png",
    "gap_peak_analysis":   "outputs/.../gap_peak_analysis/patient_gap_peak_analysis.png",
    "spatial_index_panel": "outputs/.../spatial_index/panel_spatial_index_curve_centroids_peaks.png",
    "patch_inputs": [
      "outputs/.../student_patches/patch_00/input.png",
      "outputs/.../student_patches/patch_01/input.png",
      "...",
      "outputs/.../student_patches/patch_07/input.png"
    ]
  },

  "predictions": {
    "inference_done":        true,
    "cobb_angle_deg":        32.4,
    "cobb_severity":         "moderate",
    "dominant_cluster_id":   3,
    "n_clusters_detected":   4,
    "clinical_json_path":    "outputs/.../inference/.../clinical_payload.json",
    "clinical_figure_path":  "outputs/.../inference/.../clinical_probabilistic_plot.png",
    "summary_csv_path":      "outputs/.../inference/.../clinical_summary.csv",
    "regions_csv_path":      "outputs/.../inference/.../clinical_regions.csv"
  },

  "gap_summary": {
    "mean_gap_spacing":  128.5,
    "std_gap_spacing":   14.2,
    "n_peaks":           7,
    "n_gap_peaks":       5,
    "vertebra_csv_path": "outputs/.../gap_peak_analysis/vertebra_gap_peak_analysis.csv"
  }
}
```

### Severidad del ángulo de Cobb

| `cobb_severity` | Rango |
|-----------------|-------|
| `"normal"` | < 10° |
| `"mild"` | 10° – 24° |
| `"moderate"` | 25° – 39° |
| `"severe"` | ≥ 40° |

---

## DTO FastAPI

```python
# back/app/schemas/pipeline_schema.py

class PipelineImagesDTO(BaseModel):
    combined_signal:     str | None
    analysis_grid:       str | None
    gap_peak_analysis:   str | None
    spatial_index_panel: str | None
    binary_mask:         str | None
    curve_mask:          str | None
    normalized_image:    str | None
    patch_inputs:        list[str]

class PipelinePredictionsDTO(BaseModel):
    inference_done:       bool
    cobb_angle_deg:       float | None
    cobb_severity:        str | None
    dominant_cluster_id:  int | None
    n_clusters_detected:  int | None
    clinical_json_path:   str | None
    clinical_figure_path: str | None
    summary_csv_path:     str | None
    regions_csv_path:     str | None

class PipelineGapSummaryDTO(BaseModel):
    mean_gap_spacing:  float | None
    std_gap_spacing:   float | None
    n_peaks:           int | None
    n_gap_peaks:       int | None
    vertebra_csv_path: str | None

class PipelineClinicalResultDTO(BaseModel):
    request_id:   str
    patient_name: str
    images:       PipelineImagesDTO
    predictions:  PipelinePredictionsDTO
    gap_summary:  PipelineGapSummaryDTO

    @classmethod
    def from_pipeline_output(cls, outputs: dict) -> "PipelineClinicalResultDTO": ...
```

---

## Estructura del proyecto

```
MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA/
├── back/
│   ├── app/                        ← FastAPI (controllers, services, schemas)
│   │   ├── api/v1/
│   │   │   ├── patient_controller.py
│   │   │   ├── files_controller.py
│   │   │   └── health_controller.py
│   │   └── schemas/
│   │       └── pipeline_schema.py  ← PipelineClinicalResultDTO
│   ├── pipeline_ml/                ← Pipeline ML por etapas
│   │   ├── entrypoint.py           ← run_pipeline_main() + _build_clinical_result()
│   │   ├── config.py               ← DebugFlags, RoutingFlags, PipelinePaths
│   │   ├── context.py              ← PipelineContext, AssetBundle, PipelineResult
│   │   ├── logger.py               ← PipelineLogger, timed_step
│   │   └── stages/
│   │       ├── base.py
│   │       ├── ingestion.py
│   │       ├── preprocessing.py
│   │       ├── binary_curve.py
│   │       ├── curve_refinement.py
│   │       ├── curve_patch.py
│   │       ├── student_patch.py    ← StudentUNet1CH4Heads (4 cabezas)
│   │       ├── patch_reconstruction.py  ← reconstrucción H×W + gaps/spatial
│   │       ├── inference.py        ← GMM clínico-probabilístico
│   │       ├── postprocessing.py
│   │       └── persistence.py
│   └── resources/
│       └── NORMALIZATION_PROFILES/ ← 249 perfiles .jsonl
├── front/                          ← React + Vite + shadcn/ui
├── experiments/                    ← Resultados y checkpoints de experimentos
│   └── pipeline_model/
│       ├── 01_binary_curve_cnn/    ← last_binary_curve_model.pt
│       ├── 02_student_1ch_4heads/  ← student checkpoint .pt
│       └── 04_clustering_tda/      ← region_clustering_24_types_probabilistic_bundle.joblib
├── k8s/                            ← Manifiestos Kubernetes (EKS + Minikube)
├── infra/terraform/                ← IaC AWS (EKS, ECR, ALB, S3)
└── docker-compose.yml
```

---

## Ejecución local (Docker)

```bash
# Backend + MongoDB + Redis
docker compose up --build

# Endpoints disponibles:
GET  /api/v1/health
POST /api/v1/patients          ← subida de imagen + datos del paciente
POST /api/v1/analyze           ← análisis ML (clinical_result como respuesta)
GET  /api/v1/files/{file_id}
```

### Variables de entorno requeridas

```env
MONGO_URI=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=...
```

---

## Re-exportar bundle GMM (si hay error de compatibilidad joblib)

Si el pipeline falla al cargar `clustering.joblib` con error de versión:

```python
# Ejecutar en Colab en la sesión donde tienes el bundle en memoria
import joblib
joblib.dump(bundle, "/ruta/al/region_clustering_24_types_probabilistic_bundle.joblib")
```

O instalar `dill` para mayor compatibilidad entre versiones Python:

```bash
pip install dill
```
