import { useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import CircularProgress from "@mui/material/CircularProgress";
import { AnalysisData } from "../types";

interface ImageAnalysisPanelProps {
  analysisData: AnalysisData | null;
  isAnalyzing?: boolean;
}

export function ImageAnalysisPanel({ analysisData, isAnalyzing }: ImageAnalysisPanelProps) {
  const [selectedTab, setSelectedTab] = useState(0);

  if (isAnalyzing) {
    return (
      <Box
        sx={{
          bgcolor: "background.paper",
          borderRadius: 1,
          p: 2,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 2,
        }}
      >
        <CircularProgress size={60} />
        <Typography variant="body1" sx={{ color: "text.secondary" }}>
          Analizando imagen...
        </Typography>
        <Typography variant="caption" sx={{ color: "text.secondary", textAlign: "center" }}>
          El pipeline ML está procesando la radiografía de columna vertebral.
          <br />
          Esto puede tomar varios segundos.
        </Typography>
      </Box>
    );
  }

  if (!analysisData) {
    return (
      <Box
        sx={{
          bgcolor: "background.paper",
          borderRadius: 1,
          p: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          Carga una imagen para ver el análisis
        </Typography>
      </Box>
    );
  }

  const imageViews = [
    {
      label: "Curvas (Segmentación y Original)",
      images: [
        { title: "Original", url: analysisData.originalImageUrl },
        { title: "Normalizada", url: analysisData.images.normalized_image },
      ],
    },
    {
      label: "Método automático",
      images: [
        { title: "Máscara binaria", url: analysisData.images.binary_mask },
        { title: "Máscara de curva", url: analysisData.images.curve_mask },
      ],
    },
    {
      label: "Mapa de calor",
      images: [
        { title: "Señal combinada", url: analysisData.images.combined_signal },
        { title: "Grid de análisis", url: analysisData.images.analysis_grid },
      ],
    },
  ];

  return (
    <Box
      sx={{
        bgcolor: "background.paper",
        borderRadius: 1,
        p: 2,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <Tabs
        value={selectedTab}
        onChange={(_, newValue) => setSelectedTab(newValue)}
        sx={{ borderBottom: 1, borderColor: "divider", mb: 2 }}
      >
        {imageViews.map((view, idx) => (
          <Tab key={idx} label={view.label} />
        ))}
      </Tabs>

      <Box
        sx={{
          flex: 1,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 2,
          overflow: "auto",
        }}
      >
        {imageViews[selectedTab].images.map((image, idx) => (
          <Box
            key={idx}
            sx={{
              display: "flex",
              flexDirection: "column",
              gap: 1,
            }}
          >
            <Typography variant="subtitle2" sx={{ color: "text.secondary" }}>
              {image.title}
            </Typography>
            <Box
              sx={{
                flex: 1,
                bgcolor: "black",
                borderRadius: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                overflow: "hidden",
                minHeight: 300,
              }}
            >
              {image.url ? (
                <img
                  src={image.url}
                  alt={image.title}
                  style={{
                    maxWidth: "100%",
                    maxHeight: "100%",
                    objectFit: "contain",
                  }}
                />
              ) : (
                <Typography variant="caption" sx={{ color: "grey.600" }}>
                  Sin imagen
                </Typography>
              )}
            </Box>
          </Box>
        ))}
      </Box>

      {/* Bottom info */}
      <Box
        sx={{
          mt: 2,
          p: 2,
          bgcolor: "background.default",
          borderRadius: 1,
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <Box>
          <Typography variant="caption" sx={{ color: "text.secondary" }}>
            Vista ΔD (cm)
          </Typography>
          <Typography variant="body2">25</Typography>
        </Box>
        <Box>
          <Typography variant="caption" sx={{ color: "text.secondary" }}>
            Puntos detectados
          </Typography>
          <Typography variant="body2">
            {analysisData.gap_summary.n_peaks || 0}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
