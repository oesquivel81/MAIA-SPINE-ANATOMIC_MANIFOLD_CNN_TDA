# FINAL AUDIT REPORT — pipeline_model v02A

Generated: 2026-05-20T01:03:51.025299

## Status

Final status: **PASS**

## Totals

- Total files: 27
- Total MB: 178.512
- Joblibs: 5

## Checks

- Directories OK: True
- Expected models OK: True
- No bad files: True
- Joblibs load OK: True

## Model schema

### 01_binary_curve_cnn

- Input: 1 channel
- Outputs: binary, curve

### 02_student_1ch_4heads

- Input: 1 channel
- Outputs: binary, boundary, intervertebral, ordinal

### 03_cnn_10ch_multitask

- Input: 10 channels
- Outputs: multiclass, binary, boundary, intervertebral, ordinal

### 04_clustering_tda

- Clustering/TDA artifacts, gaps, peaks and indexed vectors.

## Generated files

- audit_dirs.csv
- audit_files.csv
- audit_by_extension.csv
- audit_expected_models.csv
- audit_joblibs.csv
- audit_bad_files.csv
- final_audit_summary.json