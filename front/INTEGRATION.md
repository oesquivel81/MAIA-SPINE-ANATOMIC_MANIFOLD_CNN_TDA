# MAIA-SPINE Frontend Integration Guide

This frontend application connects to the MAIA-SPINE backend for spine analysis and scoliosis detection.

## Backend Setup

1. **Start the MAIA-SPINE backend**

   The backend should be running from the repository you cloned:
   ```bash
   cd temp_repo/back
   docker-compose up --build
   ```

   This will start:
   - FastAPI server on `http://localhost:8000`
   - MongoDB on port 27017
   - Redis on port 6379
   - LocalStack (S3) on port 4566

2. **Verify backend is running**

   Check the health endpoint:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

## Frontend Configuration

1. **Configure the API URL**

   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

   Update the API URL if your backend is running on a different host/port:
   ```
   VITE_API_URL=http://localhost:8000/api/v1
   ```

2. **Start the frontend dev server**

   The Vite dev server should already be running. If not, it will start automatically.

## API Endpoints Used

The frontend connects to these backend endpoints:

1. **POST /api/v1/patients**
   - Uploads patient image and information
   - Stores data in S3 and MongoDB
   - Returns patient ID and metadata

2. **POST /api/v1/normalization/image**
   - Processes the spine X-ray image
   - Applies normalization and preprocessing
   - Returns normalized image paths

3. **Future: Full Pipeline Endpoint**
   - The backend has the full ML pipeline at `back/pipeline_ml/entrypoint.py`
   - To get full predictions (Cobb angle, severity, etc.), you may need to:
     - Create a new endpoint that calls `run_pipeline_entry()`
     - Or extend the normalization endpoint to trigger the full pipeline

## Data Flow

```
User uploads X-ray image
        ↓
Frontend → POST /api/v1/patients (upload image + patient info)
        ↓
Frontend → POST /api/v1/normalization/image (normalize image)
        ↓
Backend runs ML pipeline:
  - Ingestion
  - Preprocessing
  - Binary curve detection
  - Curve refinement
  - Patch extraction
  - Student CNN inference
  - Patch reconstruction
  - GMM clustering inference
  - Postprocessing
        ↓
Frontend receives:
  - Normalized images
  - Binary masks
  - Curve masks
  - Predictions (Cobb angle, severity)
  - Clinical metrics
        ↓
Display results to user
```

## Current Limitations

1. **Mock Data**: The current implementation uses mock prediction data because the backend endpoints may not yet return the full `PipelineClinicalResultDTO`. To get real predictions, you'll need to:

   - Add an endpoint in `back/app/api/v1/` that calls the full pipeline
   - Example endpoint:
     ```python
     @router.post("/analyze", response_model=PipelineClinicalResultDTO)
     async def analyze_spine(
         file: UploadFile = File(...),
         full_assets: str = Form(...),
     ):
         from pipeline_ml.entrypoint import run_pipeline_entry
         
         # Read image
         image_bytes = await file.read()
         image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
         
         # Run pipeline
         result = run_pipeline_entry(
             image=image,
             full_assets=full_assets,
             config_file="/path/to/config.json"
         )
         
         return PipelineClinicalResultDTO.from_pipeline_output(result["outputs"])
     ```

2. **CORS**: Make sure CORS is enabled in your FastAPI backend:
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:5173"],  # Vite dev server
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

## Features

- ✅ Patient information form
- ✅ X-ray image upload
- ✅ Real-time image preview
- ✅ Spine diagram visualization
- ✅ Multiple image views (original, normalized, masks, heatmaps)
- ✅ Prediction results display (Cobb angle, severity, metrics)
- ✅ Clinical analysis summary
- ✅ Dark theme matching the reference design

## Next Steps

1. Add the full pipeline endpoint to the backend
2. Update `PatientUploadPanel.tsx` to call this endpoint
3. Parse and display real prediction results
4. Add image download functionality
5. Add PDF report generation
6. Implement patient history tracking
