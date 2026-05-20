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
