# Curve Analysis Report

## Objetivo

Comparar curvas CSV, curvas target derivadas de `y_region` y curvas predichas por la CNN.

Comparaciones principales:

- `csv_vs_target`
- `csv_vs_pred`
- `target_vs_pred`

## Métricas

- `mae_px`: error absoluto medio en pixeles.
- `rmse_px`: raíz del error cuadrático medio.
- `p95_abs_px`: percentil 95 del error absoluto.
- `signed_mean_px`: sesgo promedio; positivo significa curva comparada más a la derecha.
- `hausdorff_px`: distancia máxima entre curvas.
- `chamfer_px`: distancia promedio bidireccional entre curvas.
- `length_diff_pct`: diferencia porcentual de longitud.
- `curvature_mae`: diferencia media de curvatura.

## Resumen global

| comparison     |   n_patients |   mae_px_mean |   mae_px_median |   rmse_px_mean |   p95_abs_px_mean |   max_abs_px_mean |   signed_mean_px_mean |   mae_width_pct_mean |   hausdorff_px_mean |   chamfer_px_mean |   length_diff_pct_mean |   curvature_mae_mean |   corr_x_mean |
|:---------------|-------------:|--------------:|----------------:|---------------:|------------------:|------------------:|----------------------:|---------------------:|--------------------:|------------------:|-----------------------:|---------------------:|--------------:|
| csv_vs_pred    |          249 |       47.6948 |         32.9159 |        50.703  |           66.6156 |           68.1468 |             -8.10945  |             18.6308  |            103.81   |           49.3089 |              35.8226   |            0.107755  |      0.452529 |
| csv_vs_target  |          248 |       43.7519 |         27.3196 |        46.0692 |           60.5939 |           61.7823 |             -9.25917  |             17.0906  |             69.2852 |           40.6585 |              -0.278424 |            0.0905763 |      0.569909 |
| target_vs_pred |          249 |       14.1309 |         13.0565 |        16.3093 |           27.2198 |           28.4411 |              0.115978 |              5.51987 |             62.6371 |           16.5973 |              36.8675   |            0.0548699 |      0.750433 |

## Gráficas

### 01_boxplot_mae_by_comparison

![01_boxplot_mae_by_comparison](plots/01_boxplot_mae_by_comparison.png)

### 02_hist_target_vs_pred_mae

![02_hist_target_vs_pred_mae](plots/02_hist_target_vs_pred_mae.png)

### 03_hist_target_vs_pred_signed_bias

![03_hist_target_vs_pred_signed_bias](plots/03_hist_target_vs_pred_signed_bias.png)

### 04_scatter_mae_vs_hausdorff

![04_scatter_mae_vs_hausdorff](plots/04_scatter_mae_vs_hausdorff.png)

### 05_scatter_curve_mae_vs_heatmap_dice

![05_scatter_curve_mae_vs_heatmap_dice](plots/05_scatter_curve_mae_vs_heatmap_dice.png)

### 06_mean_abs_error_by_y

![06_mean_abs_error_by_y](plots/06_mean_abs_error_by_y.png)

### 07_mean_signed_error_by_y

![07_mean_signed_error_by_y](plots/07_mean_signed_error_by_y.png)

### 08_worst_25_target_vs_pred_mae

![08_worst_25_target_vs_pred_mae](plots/08_worst_25_target_vs_pred_mae.png)


## Archivos principales

```text
tables/curve_pairwise_metrics.csv
tables/curve_rowwise_errors.csv
tables/curve_heatmap_metrics.csv
tables/curve_global_summary_by_comparison.csv
plots/*.png
patients/<patient_key>/*.png
```
