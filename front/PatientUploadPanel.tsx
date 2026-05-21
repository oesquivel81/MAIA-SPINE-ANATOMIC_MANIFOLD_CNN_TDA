import { useState, ChangeEvent, FormEvent } from "react";
import Box from "@mui/material/Box";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import { PatientInfo, AnalysisData } from "../types";
import { API_BASE_URL } from "../config";

interface PatientUploadPanelProps {
  onAnalysisComplete: (data: AnalysisData) => void;
  isAnalyzing: boolean;
  setIsAnalyzing: (analyzing: boolean) => void;
}

export function PatientUploadPanel({
  onAnalysisComplete,
  isAnalyzing,
  setIsAnalyzing,
}: PatientUploadPanelProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [patientInfo, setPatientInfo] = useState<PatientInfo>({
    nombre: "",
    apellido_paterno: "",
    edad: 0,
    peso: 0,
    sexo: "M",
    fecha: new Date().toISOString().split("T")[0],
  });

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreviewUrl(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handlePatientInfoChange = (field: keyof PatientInfo, value: string | number) => {
    setPatientInfo((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedFile) return;

    setIsAnalyzing(true);
    setError(null);
    try {
      // First, upload the patient image
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("nombre", patientInfo.nombre);
      formData.append("apellido_paterno", patientInfo.apellido_paterno);
      formData.append("edad", patientInfo.edad.toString());
      formData.append("peso", patientInfo.peso.toString());
      formData.append("sexo", patientInfo.sexo);
      formData.append("fecha", patientInfo.fecha);

      const uploadResponse = await fetch(`${API_BASE_URL}/patients`, {
        method: "POST",
        body: formData,
      });

      if (!uploadResponse.ok) {
        throw new Error("Failed to upload patient data");
      }

      const uploadData = await uploadResponse.json();

      // Then, trigger the normalization/analysis
      const normalizeFormData = new FormData();
      normalizeFormData.append("file", selectedFile);
      normalizeFormData.append(
        "trace_patient_name",
        `${patientInfo.apellido_paterno}_${patientInfo.nombre}`
      );
      normalizeFormData.append("trace_patient_lastname", patientInfo.apellido_paterno);
      normalizeFormData.append("trace_sex", patientInfo.sexo);
      normalizeFormData.append("trace_age", patientInfo.edad.toString());
      normalizeFormData.append("trace_weight", patientInfo.peso.toString());
      normalizeFormData.append("trace_timestamp", patientInfo.fecha);
      normalizeFormData.append("debug_save_json", "true");
      normalizeFormData.append("trace_generate_visualization", "true");

      const normalizeResponse = await fetch(`${API_BASE_URL}/normalization/image`, {
        method: "POST",
        body: normalizeFormData,
      });

      if (!normalizeResponse.ok) {
        throw new Error("Failed to analyze image");
      }

      const normalizeData = await normalizeResponse.json();

      // ─────────────────────────────────────────────────────────────────
      // TODO: Replace this mock data with real backend response
      // ─────────────────────────────────────────────────────────────────
      // Once you add a full pipeline endpoint to the backend (see INTEGRATION.md),
      // replace this mock data with the actual PipelineClinicalResultDTO response:
      //
      // const pipelineResponse = await fetch(`${API_BASE_URL}/analyze`, {
      //   method: "POST",
      //   body: pipelineFormData,
      // });
      // const analysisData = await pipelineResponse.json();
      // onAnalysisComplete(analysisData);
      //
      // For now, using mock data to demonstrate the UI:
      const mockAnalysisData: AnalysisData = {
        request_id: uploadData.id,
        patient_name: `${patientInfo.apellido_paterno}_${patientInfo.nombre}`,
        images: {
          normalized_image: previewUrl || undefined,
          binary_mask: previewUrl || undefined,
          curve_mask: previewUrl || undefined,
          combined_signal: previewUrl || undefined,
          analysis_grid: previewUrl || undefined,
        },
        predictions: {
          inference_done: true,
          cobb_angle_deg: 23.5,
          cobb_severity: "Moderado",
          dominant_cluster_id: 2,
          n_clusters_detected: 3,
        },
        gap_summary: {
          mean_gap_spacing: 45.2,
          std_gap_spacing: 3.8,
          n_peaks: 24,
          n_gap_peaks: 23,
        },
        originalImageUrl: previewUrl || undefined,
      };

      onAnalysisComplete(mockAnalysisData);
    } catch (error) {
      console.error("Error analyzing image:", error);
      const errorMessage =
        error instanceof Error
          ? error.message
          : "Error al analizar la imagen. Verifique que el backend esté ejecutándose.";
      setError(errorMessage);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <Box
      component="form"
      onSubmit={handleSubmit}
      sx={{
        bgcolor: "background.paper",
        borderRadius: 1,
        p: 2,
        display: "flex",
        flexDirection: "column",
        gap: 2,
        overflowY: "auto",
      }}
    >
      <Typography variant="h6" sx={{ mb: 1 }}>
        Ficha / Carga imagen
      </Typography>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Image Upload */}
      <Box>
        <input
          accept="image/*"
          style={{ display: "none" }}
          id="raised-button-file"
          type="file"
          onChange={handleFileChange}
        />
        <label htmlFor="raised-button-file">
          <Button
            variant="outlined"
            component="span"
            fullWidth
            startIcon={<CloudUploadIcon />}
            sx={{ mb: 2 }}
          >
            Cargar imagen
          </Button>
        </label>

        {previewUrl && (
          <Box
            sx={{
              width: "100%",
              height: 300,
              bgcolor: "black",
              borderRadius: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              overflow: "hidden",
            }}
          >
            <img
              src={previewUrl}
              alt="Preview"
              style={{
                maxWidth: "100%",
                maxHeight: "100%",
                objectFit: "contain",
              }}
            />
          </Box>
        )}
      </Box>

      {/* Patient Information */}
      <Typography variant="subtitle2" sx={{ mt: 2 }}>
        Información del paciente
      </Typography>

      <TextField
        label="Nombre"
        value={patientInfo.nombre}
        onChange={(e) => handlePatientInfoChange("nombre", e.target.value)}
        fullWidth
        size="small"
        required
      />

      <TextField
        label="Apellido paterno"
        value={patientInfo.apellido_paterno}
        onChange={(e) => handlePatientInfoChange("apellido_paterno", e.target.value)}
        fullWidth
        size="small"
        required
      />

      <TextField
        label="Edad"
        type="number"
        value={patientInfo.edad || ""}
        onChange={(e) => handlePatientInfoChange("edad", parseInt(e.target.value) || 0)}
        fullWidth
        size="small"
        required
      />

      <TextField
        label="Peso (kg)"
        type="number"
        value={patientInfo.peso || ""}
        onChange={(e) => handlePatientInfoChange("peso", parseFloat(e.target.value) || 0)}
        fullWidth
        size="small"
        required
      />

      <FormControl fullWidth size="small">
        <InputLabel>Sexo</InputLabel>
        <Select
          value={patientInfo.sexo}
          label="Sexo"
          onChange={(e) => handlePatientInfoChange("sexo", e.target.value)}
        >
          <MenuItem value="M">Masculino</MenuItem>
          <MenuItem value="F">Femenino</MenuItem>
        </Select>
      </FormControl>

      <TextField
        label="Fecha"
        type="date"
        value={patientInfo.fecha}
        onChange={(e) => handlePatientInfoChange("fecha", e.target.value)}
        fullWidth
        size="small"
        InputLabelProps={{ shrink: true }}
        required
      />

      <Button
        type="submit"
        variant="contained"
        fullWidth
        disabled={!selectedFile || isAnalyzing}
        sx={{ mt: 2 }}
      >
        {isAnalyzing ? (
          <CircularProgress size={24} color="inherit" />
        ) : (
          "Analizar imagen"
        )}
      </Button>
    </Box>
  );
}
