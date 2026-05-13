# README - Normalizacion de Imagen en Colab

Este documento resume las clases y la secuencia de metodos del notebook `MAIIA_NORMALIZATION_IMAGE.ipynb`.

## 1. Objetivo del flujo

Normalizar imagenes de columna en escala de grises en dos fases:

1. Normalizacion espacial (resolucion): estandarizar lado largo (por defecto 1024).
2. Normalizacion de intensidad: robusta con `robust_mad` y salida final en rango aproximado `0-255`.

## 2. Clases principales

### 2.1 InlineNormalizationMasterConfig
Encapsula `MASTER_CONFIG` y expone getters de configuracion.

Metodos clave:

- `get_normalization_mode()`
- `get_p_low()`
- `get_p_high()`
- `get_mask_source()`
- `get_target_long_side()`
- `standardize_long_side()`
- `keep_aspect_ratio()`
- `pad_to_square()`
- `get_patient_json_path(patient_key)`
- `summary()`

### 2.2 ImageStats
Calcula estadisticos de la imagen.

Metodo clave:

- `compute(image)` -> min, max, mean, std, median, p1, p5, p95, p99.

### 2.3 ResolutionNormalizer
Normaliza tamano y opcionalmente padding a cuadrado.

Metodos clave:

- `normalize(image)`
- `_resize_long_side(image)`
- `_pad_to_square(image)`

Salida: imagen ajustada + metadata de escalado (`scale_x`, `scale_y`, shapes).

### 2.4 IntensityNormalizer
Normaliza intensidad con varios modos.

Metodos clave:

- `normalize(image)`
- `_percentile(image)`
- `_robust_mad(image)`
- `_minmax(image)`
- `_zscore(image)`
- `_to_uint8(image)`

Salida: imagen normalizada `uint8` + metadata de estadisticos antes/despues.

### 2.5 ImageNormalizationPipeline
Orquesta lectura, normalizacion, guardado y resumen.

Metodos clave:

- `_save_config_snapshot()`
- `read_image(image_path)`
- `infer_patient_key(image_path)`
- `find_images(input_path)`
- `normalize_one(image_path, patient_key=None)`
- `run(input_path, max_images=None)`

## 3. Secuencia de metodos (orden de ejecucion)

Secuencia recomendada del pipeline por imagen:

1. `read_image(image_path)`
2. `resolution_normalizer.normalize(image_original)`
3. `intensity_normalizer.normalize(image_resized)`
4. Guardar imagen normalizada (`cv2.imwrite`)
5. Guardar JSON de metadatos
6. Agregar fila a resumen (`summary_row`)

Secuencia por lote:

1. `find_images(input_path)`
2. Iterar imagenes
3. `normalize_one(...)` por cada imagen
4. Exportar `normalization_run_summary.csv`
5. Exportar `normalization_run_summary.jsonl`

## 4. Normalizacion por relacion detectada y aproximacion

Para "tomar la normalizacion de acuerdo a su relacion" y obtener un resultado aproximado estable, el notebook ya incluye variantes diagnosticas utiles:

- `robust_mad_normalize_historical_like(...)`
- `robust_mad_with_reference_pixels(image, ref_pixels, ...)`

### Recomendacion de criterio de relacion

Usar la siguiente jerarquia para detectar la relacion de intensidades de cada imagen:

1. Si existe mascara procesada valida, usar pixeles de mascara como referencia (`ref_pixels`).
2. Si no existe mascara, usar pixeles positivos de imagen (`image > 0`).
3. Si la imagen es casi vacia, usar toda la imagen como fallback.

Esto mantiene coherencia entre pacientes y evita sesgos por fondo negro.

### Aproximacion recomendada

1. Clip por percentiles (`p_low`, `p_high`).
2. Calcular mediana y MAD en `ref_pixels`.
3. Aplicar robust z-score y clip de z (ejemplo `[-4, 4]`).
4. Hacer estiramiento final min-max del robust-z recortado para cubrir mejor `0-255`.
5. Convertir a `uint8` con control de NaN/Inf.

Este esquema es una aproximacion robusta al comportamiento historico y reduce variacion entre estudios.

## 5. Parametros sugeridos

- `mode`: `robust_mad`
- `p_low`: `1.0`
- `p_high`: `99.0`
- `target_long_side`: `1024`
- `z_clip`: `4.0` (en variante historica)

## 6. Salidas esperadas

En el directorio de salida:

- `normalized_images/*.png`
- `normalization_json/*_normalization_info.json`
- `config_snapshot/master_config_used.json`
- `normalization_run_summary.csv`
- `normalization_run_summary.jsonl`

## 7. Nota practica

Si buscas maxima comparabilidad con corridas antiguas, prioriza la variante historica (`robust_mad_normalize_historical_like`) o la variante con pixeles de referencia (`robust_mad_with_reference_pixels`) usando mascara cuando este disponible.