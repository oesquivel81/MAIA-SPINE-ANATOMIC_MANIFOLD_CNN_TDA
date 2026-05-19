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
| csv_vs_pred    |          249 |       47.171  |         32.5367 |        50.0956 |           66.7567 |           69.0233 |              -8.10345 |             18.4262  |            104.295  |           48.0525 |              47.5975   |            0.148769  |      0.39579  |
| csv_vs_target  |          248 |       43.7519 |         27.3196 |        46.0692 |           60.5939 |           61.7823 |              -9.25917 |             17.0906  |             69.2852 |           40.6585 |              -0.278424 |            0.0905763 |      0.569909 |
| target_vs_pred |          249 |       13.1147 |         12.1833 |        15.7834 |           29.6854 |           32.0912 |               0.43426 |              5.12291 |             63.1575 |           15.2734 |              49.1192   |            0.119239  |      0.546472 |

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
