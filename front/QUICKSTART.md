# Quick Start Guide

Get the MAIA-SPINE frontend up and running in minutes.

## Step 1: Start the Backend

Navigate to your MAIA-SPINE backend repository and start the services:

```bash
cd /path/to/MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA/back
docker-compose up
```

Wait until you see:
```
fastapi_spring_style_api | INFO:     Application startup complete.
```

Verify it's running:
```bash
curl http://localhost:8000/api/v1/health
```

Expected response:
```json
{"status": "healthy"}
```

## Step 2: Configure the Frontend

The frontend is already configured to connect to `http://localhost:8000`.

If your backend is on a different host/port:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set:
   ```
   VITE_API_URL=http://your-backend-host:8000/api/v1
   ```

## Step 3: Test the Application

The Vite dev server should already be running. Open your browser and:

1. **Upload a test image**
   - Click "Cargar imagen"
   - Select a spine X-ray image (JPG, PNG)
   - You should see a preview

2. **Fill patient information**
   - Nombre: Juan
   - Apellido paterno: Pérez
   - Edad: 45
   - Peso: 70
   - Sexo: M (Masculino)
   - Fecha: (today's date is pre-filled)

3. **Analyze the image**
   - Click "Analizar imagen"
   - Wait for the analysis (this may take 30-60 seconds)
   - You should see:
     - Loading indicator in the image panel
     - "Analizando imagen..." message

4. **View results**
   After analysis completes, you'll see:
   - Spine diagram with highlighted vertebrae
   - Multiple image views (original, masks, heatmaps)
   - Clinical predictions:
     - Cobb angle in degrees
     - Severity classification
     - Vertebrae count
     - Gap spacing metrics

## What You Should See

### Before Analysis
- Empty state: "Carga una imagen para ver el análisis"
- Patient form on the left
- Spine diagram (greyed out)

### During Analysis
- Loading spinner in image panel
- "Analizando imagen..." message
- Upload panel shows CircularProgress

### After Analysis
- ✅ Spine diagram with highlighted regions
- ✅ Multiple image tabs:
  - "Curvas (Segmentación y Original)"
  - "Método automático"
  - "Mapa de calor"
- ✅ Prediction results panel at bottom:
  - Cobb angle
  - Severity
  - Detailed metrics
  - Analysis steps checklist

## Current Limitations (Mock Data)

⚠️ **Important**: The frontend currently uses **mock prediction data** because the full pipeline endpoint hasn't been created yet.

What works:
- ✅ Patient upload to backend
- ✅ Image normalization via backend
- ✅ UI displays properly
- ✅ All components render correctly

What's mocked:
- ❌ Cobb angle (shows 23.5° as example)
- ❌ Severity (shows "Moderado" as example)
- ❌ Processed images (shows original image copies)

To get real predictions, see:
- [BACKEND_CONNECTION.md](./BACKEND_CONNECTION.md) - Create the analysis endpoint
- [INTEGRATION.md](./INTEGRATION.md) - Integration guide

## Testing with Real Backend (Once Configured)

When you create the `/spine/analyze` endpoint:

1. Update `src/app/components/PatientUploadPanel.tsx`
2. Replace the mock data section (line ~125) with the real API call
3. Test with a spine X-ray image
4. Real predictions should appear

## Troubleshooting

### "Failed to fetch"
- Backend not running → Start docker-compose
- CORS issue → Add CORS middleware to FastAPI
- Wrong URL → Check VITE_API_URL in .env

### Images not displaying
- Check browser console for errors
- Verify image paths in network tab
- Ensure static files are served

### Analysis takes too long
- ML pipeline is computationally intensive
- Expected: 30-60 seconds for full analysis
- Check backend logs: `docker-compose logs -f api`

### Error alerts appear
- Red alert banner shows error details
- Check backend logs for stack traces
- Verify model files exist at specified paths

## Next Steps

1. ✅ Test the current UI with mock data
2. 📝 Create the `/spine/analyze` endpoint
3. 🔗 Connect frontend to real predictions
4. 📊 Verify Cobb angle calculations
5. 🎨 Customize theme if needed
6. 📄 Add PDF report generation

## Sample Test Data

If you need test spine X-ray images:
1. Use images from the MAIA-SPINE dataset
2. Look for files like `S_26.jpg` in the repository
3. Ensure images are grayscale or will be converted

## Support

- UI/Frontend issues → Check browser console
- Backend issues → Check `docker-compose logs -f`
- Integration questions → See [INTEGRATION.md](./INTEGRATION.md)

Happy testing! 🚀
