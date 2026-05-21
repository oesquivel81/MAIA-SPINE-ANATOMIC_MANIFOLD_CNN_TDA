import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { AnalysisData } from "../types";

interface SpineDiagramProps {
  analysisData: AnalysisData | null;
}

export function SpineDiagram({ analysisData }: SpineDiagramProps) {
  // Vertebrae segments
  const cervicalVertebrae = ["C1", "C2", "C3", "C4", "C5", "C6", "C7"];
  const thoracicVertebrae = Array.from({ length: 12 }, (_, i) => `T${i + 1}`);
  const lumbarVertebrae = ["L1", "L2", "L3", "L4", "L5"];
  const sacralVertebrae = ["S1", "S2", "S3", "S4", "S5"];

  const renderVertebra = (label: string, highlighted: boolean = false) => (
    <Box
      key={label}
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        my: 0.3,
      }}
    >
      {/* Vertebra body */}
      <Box
        sx={{
          width: 40,
          height: 20,
          bgcolor: highlighted ? "primary.main" : "grey.700",
          borderRadius: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: highlighted ? 2 : 1,
          borderColor: highlighted ? "primary.light" : "grey.600",
          position: "relative",
          boxShadow: highlighted ? "0 0 10px rgba(59, 130, 246, 0.5)" : "none",
          transition: "all 0.2s ease",
          "&:hover": {
            transform: "scale(1.1)",
            boxShadow: "0 0 15px rgba(59, 130, 246, 0.7)",
          },
        }}
      >
        <Typography variant="caption" sx={{ fontSize: "0.65rem", fontWeight: 600, zIndex: 1 }}>
          {label}
        </Typography>

        {/* Spinous process (back extension) */}
        <Box
          sx={{
            position: "absolute",
            right: -8,
            width: 8,
            height: 12,
            bgcolor: highlighted ? "primary.dark" : "grey.800",
            borderRadius: "0 2px 2px 0",
            opacity: 0.7,
          }}
        />
      </Box>
    </Box>
  );

  return (
    <Box
      sx={{
        bgcolor: "background.paper",
        borderRadius: 1,
        p: 2,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        overflowY: "auto",
      }}
    >
      <Typography variant="h6" sx={{ mb: 2 }}>
        Imagen original
      </Typography>

      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 1,
        }}
      >
        {/* Cervical */}
        <Typography variant="caption" sx={{ color: "text.secondary", mb: 0.5 }}>
          Cervical
        </Typography>
        {cervicalVertebrae.map((v) => renderVertebra(v))}

        {/* Thoracic */}
        <Typography variant="caption" sx={{ color: "text.secondary", mt: 2, mb: 0.5 }}>
          Torácica
        </Typography>
        {thoracicVertebrae.map((v, idx) => renderVertebra(v, analysisData && idx >= 4 && idx <= 8))}

        {/* Lumbar */}
        <Typography variant="caption" sx={{ color: "text.secondary", mt: 2, mb: 0.5 }}>
          Lumbar
        </Typography>
        {lumbarVertebrae.map((v) => renderVertebra(v))}

        {/* Sacral */}
        <Typography variant="caption" sx={{ color: "text.secondary", mt: 2, mb: 0.5 }}>
          Sacro
        </Typography>
        {sacralVertebrae.map((v) => renderVertebra(v))}
      </Box>

      {analysisData && (
        <Box sx={{ mt: 3, textAlign: "center" }}>
          <Typography variant="caption" sx={{ color: "primary.main" }}>
            Número de vértebras: {analysisData.gap_summary.n_peaks || 24}
          </Typography>
        </Box>
      )}
    </Box>
  );
}
