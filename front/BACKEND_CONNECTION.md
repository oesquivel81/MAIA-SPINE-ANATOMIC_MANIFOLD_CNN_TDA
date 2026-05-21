# Connecting Frontend to Backend Predictions

This guide explains how to connect the frontend to receive real predictions from the MAIA-SPINE backend.

## Current Status

The frontend is currently using **mock data** for predictions. To get real predictions, you need to create a backend endpoint that runs the full ML pipeline.

## Backend Endpoint Needed

Add this endpoint to your FastAPI backend in `back/app/api/v1/`:

### Create `spine_analysis_controller.py`

```python
import logging
import cv2
import numpy as np
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from app.schemas.pipeline_schema import PipelineClinicalResultDTO

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/analyze", response_model=PipelineClinicalResultDTO)
async def analyze_spine(
    file: UploadFile = File(..., description="Radiografía de columna"),
    nombre: str = Form(...),
    apellido_paterno: str = Form(...),
    edad: int = Form(...),
    peso: float = Form(...),
    sexo: str = Form(...),
    fecha: str = Form(...),
):
    """
    Ejecuta el pipeline ML completo para análisis de escoliosis.
    Devuelve predicciones clínicas, imágenes procesadas y métricas.
    """
    try:
        # 1. Leer imagen
        image_bytes = await file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        if image is None:
            raise HTTPException(status_code=400, detail="No se pudo decodificar la imagen")
        
        # 2. Construir assets string (ajusta las rutas a tus modelos)
        # Formato: NOMBRE|joblib1;joblib2;joblib3|recurso1;recurso2
        full_name = f"{apellido_paterno}_{nombre}"
        
        # Estas rutas deben apuntar a tus modelos entrenados
        cnn_curve_path = "/app/models/cnn_curve_binary.pt"
        student_path = "/app/models/student_unet_4heads.pt"
        clustering_path = "/app/models/clustering_gmm.joblib"
        
        full_assets = f"{full_name}|{cnn_curve_path};{student_path};{clustering_path}|"
        
        # 3. Configuración del pipeline
        config_file = "/app/config/pipeline_config.json"  # Ajusta según tu configuración
        
        # 4. Ejecutar pipeline
        from pipeline_ml.entrypoint import run_pipeline_entry
        
        result = run_pipeline_entry(
            image=image,
            full_assets=full_assets,
            config_file=config_file,
            request_id=None  # Se genera automáticamente
        )
        
        # 5. Construir respuesta
        if not result.get("ok", False):
            raise HTTPException(
                status_code=500, 
                detail=f"Pipeline falló: {result.get('message', 'Error desconocido')}"
            )
        
        outputs = result.get("outputs", {})
        clinical_result = outputs.get("clinical_result", {})
        
        # 6. Convertir a DTO
        response = PipelineClinicalResultDTO.from_pipeline_output(outputs)
        
        logger.info(
            f"Análisis completado: request_id={response.request_id}, "
            f"cobb_angle={response.predictions.cobb_angle_deg}°"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error en análisis de columna: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

### Register the router in `back/app/api/v1/router.py`

```python
from app.api.v1.spine_analysis_controller import router as spine_router

api_v1_router.include_router(spine_router, prefix="/spine", tags=["spine-analysis"])
```

### Enable CORS in `back/app/main.py`

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Frontend Integration

Once the backend endpoint is ready, update `src/app/components/PatientUploadPanel.tsx`:

### Replace the mock data section with:

```typescript
// Call the full pipeline analysis endpoint
const analysisFormData = new FormData();
analysisFormData.append("file", selectedFile);
analysisFormData.append("nombre", patientInfo.nombre);
analysisFormData.append("apellido_paterno", patientInfo.apellido_paterno);
analysisFormData.append("edad", patientInfo.edad.toString());
analysisFormData.append("peso", patientInfo.peso.toString());
analysisFormData.append("sexo", patientInfo.sexo);
analysisFormData.append("fecha", patientInfo.fecha);

const analysisResponse = await fetch(`${API_BASE_URL}/spine/analyze`, {
  method: "POST",
  body: analysisFormData,
});

if (!analysisResponse.ok) {
  throw new Error("Failed to analyze spine image");
}

const analysisData: AnalysisData = await analysisResponse.json();

// Add the original image URL to the response
analysisData.originalImageUrl = previewUrl || undefined;

onAnalysisComplete(analysisData);
```

## Testing the Connection

1. **Start the backend:**
   ```bash
   cd temp_repo/back
   docker-compose up
   ```

2. **Verify the endpoint:**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

3. **Start the frontend** (already running in Figma Make)

4. **Test with a sample X-ray:**
   - Upload a spine X-ray image
   - Fill in patient information
   - Click "Analizar imagen"
   - Wait for the pipeline to complete
   - View the results

## Expected Response Format

The backend should return a `PipelineClinicalResultDTO` with this structure:

```json
{
  "request_id": "uuid-string",
  "patient_name": "APELLIDO_NOMBRE",
  "images": {
    "combined_signal": "/path/to/combined_signal.png",
    "analysis_grid": "/path/to/analysis_grid.png",
    "gap_peak_analysis": "/path/to/gap_peak_analysis.png",
    "spatial_index_panel": "/path/to/spatial_index_panel.png",
    "binary_mask": "/path/to/binary_mask.png",
    "curve_mask": "/path/to/curve_mask.png",
    "normalized_image": "/path/to/normalized_image.png",
    "patch_inputs": ["/path/to/patch_00/input.png", ...]
  },
  "predictions": {
    "inference_done": true,
    "cobb_angle_deg": 23.5,
    "cobb_severity": "Moderado",
    "dominant_cluster_id": 2,
    "n_clusters_detected": 3,
    "clinical_json_path": "/path/to/clinical.json",
    "clinical_figure_path": "/path/to/clinical_plot.png",
    "summary_csv_path": "/path/to/summary.csv",
    "regions_csv_path": "/path/to/regions.csv"
  },
  "gap_summary": {
    "mean_gap_spacing": 45.2,
    "std_gap_spacing": 3.8,
    "n_peaks": 24,
    "n_gap_peaks": 23,
    "vertebra_csv_path": "/path/to/vertebra.csv"
  }
}
```

## Image Path Handling

The backend returns local file paths for images. You have two options:

### Option 1: Serve images as static files

Configure FastAPI to serve the artifacts directory:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/artifacts", StaticFiles(directory="/path/to/artifacts"), name="artifacts")
```

Then in the frontend, convert paths to URLs:
```typescript
const imageUrl = path.replace("/app/artifacts", "http://localhost:8000/artifacts");
```

### Option 2: Return base64-encoded images

Modify the backend to encode images as base64 strings:

```python
import base64

def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"

# In the response
images.normalized_image = encode_image(normalized_image_path)
```

## Troubleshooting

### CORS Errors
- Verify CORS middleware is configured
- Check that the frontend URL is in `allow_origins`

### 500 Internal Server Error
- Check backend logs: `docker-compose logs -f api`
- Verify model files exist at the specified paths
- Ensure config.json has correct settings

### Slow Response
- The ML pipeline can take 30-60 seconds for a full analysis
- Consider adding a WebSocket or polling mechanism for progress updates

### Image Display Issues
- Verify image paths are accessible from the frontend
- Check that static file serving is configured correctly
- Use browser DevTools to inspect network requests
