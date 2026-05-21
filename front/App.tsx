import { useState } from "react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import { PatientUploadPanel } from "./components/PatientUploadPanel";
import { SpineDiagram } from "./components/SpineDiagram";
import { ImageAnalysisPanel } from "./components/ImageAnalysisPanel";
import { PredictionResults } from "./components/PredictionResults";
import { AnalysisData } from "./types";

const darkTheme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: "#3b82f6",
    },
    background: {
      default: "#0a0e1a",
      paper: "#131829",
    },
  },
});

export default function App() {
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Box
        sx={{
          width: "100vw",
          height: "100vh",
          bgcolor: "background.default",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <Box
          sx={{
            p: 2,
            borderBottom: 1,
            borderColor: "divider",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <Box
              component="span"
              sx={{
                fontSize: "1.25rem",
                fontWeight: 600,
                color: "primary.main",
              }}
            >
              Segmentación de columna vertebral
            </Box>
          </Box>
          <Box sx={{ display: "flex", gap: 2 }}>
            <Box
              component="span"
              sx={{ fontSize: "0.875rem", color: "text.secondary" }}
            >
              Modelo entrenado
            </Box>
            <Box
              component="span"
              sx={{ fontSize: "0.875rem", color: "text.secondary" }}
            >
              Nueva consulta
            </Box>
          </Box>
        </Box>

        {/* Main Content */}
        <Box
          sx={{
            flex: 1,
            display: "grid",
            gridTemplateColumns: "320px 1fr 2fr",
            gap: 2,
            p: 2,
            overflow: "hidden",
          }}
        >
          {/* Left Panel - Patient Upload */}
          <PatientUploadPanel
            onAnalysisComplete={setAnalysisData}
            isAnalyzing={isAnalyzing}
            setIsAnalyzing={setIsAnalyzing}
          />

          {/* Center - Spine Diagram */}
          <SpineDiagram analysisData={analysisData} />

          {/* Right - Image Analysis */}
          <ImageAnalysisPanel
            analysisData={analysisData}
            isAnalyzing={isAnalyzing}
          />
        </Box>

        {/* Bottom - Prediction Results */}
        {analysisData && <PredictionResults analysisData={analysisData} />}
      </Box>
    </ThemeProvider>
  );
}