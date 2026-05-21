import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { AnalysisData } from "../types";

interface PredictionResultsProps {
  analysisData: AnalysisData;
}

export function PredictionResults({ analysisData }: PredictionResultsProps) {
  const { predictions, gap_summary } = analysisData;

  const metrics = [
    {
      label: "Estructuras detectadas",
      value: gap_summary.n_peaks || 0,
      unit: "",
    },
    {
      label: "Centros vertebrales",
      value: gap_summary.n_gap_peaks || 0,
      unit: "",
    },
    {
      label: "Contorno cervical",
      value: "55",
      unit: "%",
    },
    {
      label: "Estenosis columna",
      value: "12",
      unit: "%",
    },
    {
      label: "Ángulo de Cobb",
      value: predictions.cobb_angle_deg?.toFixed(1) || "0.0",
      unit: "°",
      highlight: true,
    },
    {
      label: "Severidad",
      value: predictions.cobb_severity || "N/A",
      unit: "",
      highlight: true,
    },
  ];

  const detailedMetrics = [
    { label: "Inter-horno", value: "0.00" },
    { label: "Vértebras detectadas", value: gap_summary.n_peaks || 0 },
    { label: "Centroides vert.", value: gap_summary.n_gap_peaks || 0 },
    { label: "Espaciado medio", value: gap_summary.mean_gap_spacing?.toFixed(1) || "0.0" },
    { label: "Desv. estándar", value: gap_summary.std_gap_spacing?.toFixed(1) || "0.0" },
    { label: "Clusters detectados", value: predictions.n_clusters_detected || 0 },
  ];

  const analysisSteps = [
    { label: "Detección curva", checked: true },
    { label: "Estrategia de parches", checked: true },
    { label: "Reconstruir mapa de cal...", checked: true },
    { label: "Localizar vértebras (pdf)", checked: true },
    { label: "Generar reporte (pdf)", checked: false },
  ];

  return (
    <Box
      sx={{
        bgcolor: "background.paper",
        borderTop: 1,
        borderColor: "divider",
        p: 2,
      }}
    >
      <Grid container spacing={2}>
        {/* Main Metrics */}
        <Grid item xs={12}>
          <Typography variant="subtitle2" sx={{ mb: 1, color: "text.secondary" }}>
            Análisis probabilístico
          </Typography>
          <Grid container spacing={2}>
            {metrics.map((metric, idx) => (
              <Grid item xs={2} key={idx}>
                <Paper
                  sx={{
                    p: 1.5,
                    textAlign: "center",
                    bgcolor: metric.highlight ? "primary.dark" : "background.default",
                    border: metric.highlight ? 1 : 0,
                    borderColor: "primary.main",
                  }}
                >
                  <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
                    {metric.label}
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      mt: 0.5,
                      color: metric.highlight ? "primary.light" : "text.primary",
                      fontWeight: 600,
                    }}
                  >
                    {metric.value}
                    {metric.unit && (
                      <Typography component="span" variant="caption" sx={{ ml: 0.5 }}>
                        {metric.unit}
                      </Typography>
                    )}
                  </Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </Grid>

        {/* Detailed Metrics */}
        <Grid item xs={6}>
          <Typography variant="subtitle2" sx={{ mb: 1, color: "text.secondary" }}>
            Métricas detalladas
          </Typography>
          <Grid container spacing={1}>
            {detailedMetrics.map((metric, idx) => (
              <Grid item xs={4} key={idx}>
                <Box sx={{ p: 1, bgcolor: "background.default", borderRadius: 1 }}>
                  <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
                    {metric.label}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 0.5 }}>
                    {metric.value}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Grid>

        {/* Analysis Steps */}
        <Grid item xs={3}>
          <Typography variant="subtitle2" sx={{ mb: 1, color: "text.secondary" }}>
            Etapas realizadas
          </Typography>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
            {analysisSteps.map((step, idx) => (
              <Box key={idx} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <CheckCircleIcon
                  sx={{
                    fontSize: 16,
                    color: step.checked ? "success.main" : "grey.600",
                  }}
                />
                <Typography
                  variant="caption"
                  sx={{
                    color: step.checked ? "text.primary" : "text.secondary",
                  }}
                >
                  {step.label}
                </Typography>
              </Box>
            ))}
          </Box>
        </Grid>

        {/* Action Buttons */}
        <Grid item xs={3}>
          <Typography variant="subtitle2" sx={{ mb: 1, color: "text.secondary" }}>
            Acciones
          </Typography>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <Box
              sx={{
                p: 1,
                bgcolor: "primary.dark",
                borderRadius: 1,
                textAlign: "center",
                cursor: "pointer",
                "&:hover": { bgcolor: "primary.main" },
              }}
            >
              <Typography variant="caption">Descargar mapa de calor</Typography>
            </Box>
            <Box
              sx={{
                p: 1,
                bgcolor: "background.default",
                borderRadius: 1,
                textAlign: "center",
                cursor: "pointer",
                "&:hover": { bgcolor: "grey.800" },
              }}
            >
              <Typography variant="caption">Descargar reporte (PDF)</Typography>
            </Box>
            <Box
              sx={{
                p: 1,
                bgcolor: "background.default",
                borderRadius: 1,
                textAlign: "center",
                cursor: "pointer",
                "&:hover": { bgcolor: "grey.800" },
              }}
            >
              <Typography variant="caption">Guardar como (JSON)</Typography>
            </Box>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
