# Pipeline Model v02A

Este directorio concentra los artefactos necesarios del pipeline experimental `v02A`.

## Estructura

### 01_binary_curve_cnn

CNN independiente de 1 entrada y 2 salidas.

Salidas esperadas:

- binary
- curve

### 02_student_1ch_4heads

Student de 1 canal y 4 cabezales.

Modelo:

- StudentUNet1CH4Heads

Entrada esperada:

- 1 canal

Salidas esperadas:

- binary
- boundary
- intervertebral
- ordinal

### 03_cnn_10ch_multitask

CNN multitarea de 10 canales.

Modelo:

- OldPatchMultiHeadUNet

Canales esperados:

- CH0 robust_mad_image
- CH1 band_mask
- CH2 balanced_edge
- CH3 oriented_centered_edge
- CH4 distance_score_band
- CH5 t_map_band
- CH6 normal_x_band
- CH7 normal_y_band
- CH8 tangent_x_band
- CH9 tangent_y_band

Salidas esperadas:

- multiclass
- binary
- boundary
- intervertebral
- ordinal

### 04_clustering_tda

Incluye modelos y tablas para clustering/TDA, gaps, peaks y vectores indexados.

### 05_reconstruction_examples

Incluye ejemplos de reconstrucción global desde patches, como `S_100`.

## Nota

No se copian los KFold pesados ni los 106 checkpoints completos del student.
Se conserva el manifest para trazabilidad.

## Generado

2026-05-20T00:45:46.951764
