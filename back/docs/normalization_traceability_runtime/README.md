# Normalization Runtime + Traceability

Este directorio documenta la adaptacion de normalizacion dinamica con trazabilidad end-to-end.

## Objetivo

- Leer perfiles desde `back/resources/NORMALIZATION_PROFILES`.
- Cargar perfiles en Redis al arranque para evitar releer JSON en cada invocacion.
- Seleccionar dinamicamente el perfil mas cercano para normalizar.
- Generar trazabilidad con:
  - carpeta por invocacion,
  - ruta B local (`JSON` o `CSV`),
  - registro opcional en Redis,
  - registro opcional en Mongo.
- Loggear al inicio de metodos clave con formato clase.metodo.
- Encender/apagar debug con bandera `true/false` en propiedades.

## Clases nuevas

- `pipeline_ml/normalization_stage/dynamic_engine.py`
  - `DynamicNormalizationEngine.select_closest_profile(...)`
  - `DynamicNormalizationEngine.run(...)`
- `pipeline_ml/normalization_stage/traceability.py`
  - `NormalizationTraceabilityService.build_identity(...)`
  - `NormalizationTraceabilityService.persist_trace(...)`
- `pipeline_ml/normalization_stage/logger.py`
  - `log_method_start(...)`

## Integraciones realizadas

- `NormalizationService` ahora:
  - usa `DynamicNormalizationEngine` para seleccion y ejecucion,
  - usa `NormalizationTraceabilityService` para persistencia de trazas,
  - recibe metadatos de paciente para armar id/carpeta,
  - soporta bandera `debug_save_json` por invocacion.

- `NormalizationProfileLoader` ahora loggea inicio de metodos.

- `normalization_controller.py` ahora acepta campos de trazabilidad:
  - `trace_patient_name`
  - `trace_patient_lastname`
  - `trace_sex`
  - `trace_age`
  - `trace_weight`
  - `trace_timestamp`
  - `debug_save_json`

## Formato de trazabilidad

- Folder: `nombre + apellido + sexo + peso + timestamp`
- ID documento: `nombre + sexo + edad + peso + timestamp`

Ejemplo:
- Folder: `juanperezm75_20260519_101530`
- ID: `juanm3275_20260519_101530`

## Banderas en propiedades (`application.properties`)

- `NORMALIZATION_DEBUG_ENABLED=true|false`
- `NORMALIZATION_DEBUG_SAVE_JSON=true|false`
- `NORMALIZATION_TRACEABILITY_ENABLED=true|false`
- `NORMALIZATION_TRACEABILITY_OUTPUT_DIR=normalization_traceability`
- `NORMALIZATION_TRACE_REDIS_ENABLED=true|false`
- `NORMALIZATION_TRACE_MONGO_ENABLED=true|false`
- `NORMALIZATION_TRACE_ROUTE_B_ENABLED=true|false`
- `NORMALIZATION_TRACE_ROUTE_B_FORMAT=auto|json|csv|both`
- `REDIS_NORMALIZATION_TRACE_PREFIX=normalization_trace`
- `MONGO_NORMALIZATION_TRACES_COLLECTION=normalization_traces`

Notas:
- Si `NORMALIZATION_TRACE_ROUTE_B_FORMAT=auto`: con `debug_save_json=true` guarda JSON; con `debug_save_json=false` guarda CSV.
- Si Redis/Mongo estan deshabilitados o no disponibles, no se rompe la ejecucion; se registra warning en `traceability.trace_warnings`.

## Dos comandos solicitados

1. Comando de carga de perfiles a Redis/Mongo (bootstrap):

```bash
cd back
python scripts/normalization_bootstrap_profiles.py
```

2. Comando de debug tipo Colab con logs y salida JSON de traza:

```bash
cd back
python scripts/normalization_debug_colab.py \
  --image "C:/ruta/imagen.png" \
  --profile-source redis \
  --name Ana \
  --lastname Lopez \
  --sex F \
  --age 31 \
  --weight 62 \
  --debug-save-json
```

## Referencia del cuaderno usado para la conversion conceptual

Notebook base: `back/resources/colab/MAIIA_NORMALIZATION_IMAGE.ipynb`

Elementos tomados como base conceptual:
- `InlineNormalizationMasterConfig`
- `ImageNormalizationPipeline`
- `robust_mad_normalize(...)`
- Export de perfiles `normalization_profile_index.jsonl`

La implementacion backend usa el mismo enfoque: seleccion de perfil + normalizacion robusta + metadata y trazabilidad.
