# MAIA-SPINE Frontend

A modern web application for spine analysis and scoliosis detection, built with React, Material-UI, and TypeScript.

## Overview

This application provides a user-friendly interface for the MAIA-SPINE (Anatomic Manifold CNN + TDA) backend system. It allows healthcare professionals to:

- Upload spine X-ray images
- Input patient information
- Analyze images using deep learning models
- View segmentation results and clinical predictions
- Review Cobb angle measurements and severity classifications
- Access detailed metrics and visualizations

## Features

✨ **Patient Management**
- Patient information form (name, age, weight, sex, date)
- X-ray image upload with preview
- Secure data transmission to backend

📊 **Analysis & Visualization**
- Real-time image processing status
- Interactive spine diagram showing vertebrae
- Multiple image views:
  - Original and normalized images
  - Binary and curve masks
  - Heatmaps and analysis grids
  - Combined signal visualization

🎯 **Clinical Predictions**
- Cobb angle measurement (degrees)
- Severity classification (Leve, Moderado, Severo)
- Vertebrae detection count
- Gap spacing metrics
- Cluster analysis results

🎨 **Modern UI**
- Dark theme optimized for medical imaging
- Responsive grid layout
- Material Design components
- Professional color scheme matching radiology software

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Material-UI (MUI) v7** - Component library
- **Vite 6** - Build tool and dev server
- **Tailwind CSS v4** - Utility-first styling

## Getting Started

### Prerequisites

- Node.js 18+ (or use the included runtime)
- pnpm package manager
- MAIA-SPINE backend running (see [INTEGRATION.md](./INTEGRATION.md))

### Installation

Dependencies are already installed. If you need to reinstall:

```bash
pnpm install
```

### Configuration

1. Copy the environment example:
   ```bash
   cp .env.example .env
   ```

2. Update the backend API URL in `.env`:
   ```
   VITE_API_URL=http://localhost:8000/api/v1
   ```

### Running the Application

The Vite dev server is managed by Figma Make and runs automatically.

If you need to run it manually:
```bash
pnpm run dev
```

## Project Structure

```
src/
├── app/
│   ├── App.tsx                    # Main application component
│   ├── config.ts                  # API configuration
│   ├── types.ts                   # TypeScript type definitions
│   └── components/
│       ├── PatientUploadPanel.tsx # Patient info & image upload
│       ├── SpineDiagram.tsx       # Interactive spine visualization
│       ├── ImageAnalysisPanel.tsx # Image display with tabs
│       └── PredictionResults.tsx  # Clinical metrics display
├── imports/                        # Asset imports (Figma frames, etc.)
└── styles/                         # CSS and theme files
```

## Backend Integration

### Current Status

The frontend uses **mock data** for demonstration purposes. To get real predictions:

1. **Start the MAIA-SPINE backend**
   ```bash
   cd path/to/MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA/back
   docker-compose up
   ```

2. **Create the analysis endpoint** (see [BACKEND_CONNECTION.md](./BACKEND_CONNECTION.md))

3. **Update the frontend** to call the real endpoint

For detailed integration instructions, see:
- [INTEGRATION.md](./INTEGRATION.md) - Complete integration guide
- [BACKEND_CONNECTION.md](./BACKEND_CONNECTION.md) - Backend endpoint setup

## API Endpoints Used

The frontend connects to these backend endpoints:

- `POST /api/v1/patients` - Upload patient data and X-ray image
- `POST /api/v1/normalization/image` - Normalize and preprocess image
- `POST /api/v1/spine/analyze` - (To be created) Run full ML pipeline

## Development

### Key Components

**PatientUploadPanel**
- Handles file upload and patient data collection
- Sends data to backend
- Shows loading states and error messages

**SpineDiagram**
- Displays vertebrae from C1 to S5
- Highlights affected regions
- Interactive hover effects

**ImageAnalysisPanel**
- Tabbed interface for different image views
- Supports original, processed, and heatmap views
- Loading states during analysis

**PredictionResults**
- Displays clinical metrics (Cobb angle, severity, etc.)
- Shows analysis pipeline steps
- Action buttons for downloads and exports

### Type Definitions

All API response types are defined in `src/app/types.ts`:
- `AnalysisData` - Complete analysis result
- `PipelineImages` - Generated image paths
- `PipelinePredictions` - Clinical predictions
- `GapSummary` - Vertebrae gap metrics

## Customization

### Changing the Theme

Edit `src/app/App.tsx` to modify the Material-UI theme:

```typescript
const darkTheme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#3b82f6" },
    background: {
      default: "#0a0e1a",
      paper: "#131829",
    },
  },
});
```

### Adding New Metrics

1. Update types in `src/app/types.ts`
2. Add fields to the display in `PredictionResults.tsx`
3. Ensure backend returns the new data

## Troubleshooting

### Backend Connection Issues

**CORS Errors:**
- Verify CORS is enabled in the backend
- Check that frontend URL is allowed in `allow_origins`

**Connection Refused:**
- Ensure backend is running: `curl http://localhost:8000/api/v1/health`
- Verify the API URL in `.env`

### Image Display Issues

**Images not showing:**
- Check that image paths from backend are accessible
- Verify static file serving is configured
- Use browser DevTools to inspect network requests

**Slow Loading:**
- ML pipeline can take 30-60 seconds
- Loading indicator will show during processing

## Architecture

```
┌─────────────────┐
│   User Browser  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  React Frontend │ (This application)
│   - Upload UI   │
│   - Display     │
│   - Validation  │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────┐
│  FastAPI Backend│
│   - Upload      │
│   - ML Pipeline │
│   - Storage     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ML Pipeline    │
│   - CNN Models  │
│   - GMM Cluster │
│   - TDA         │
└─────────────────┘
```

## License

This frontend application is part of the MAIA-SPINE project. Check the main repository for license information.

## Support

For issues related to:
- **Frontend UI/UX**: Create an issue in this repository
- **Backend/ML Pipeline**: Refer to the MAIA-SPINE repository
- **Integration**: See [INTEGRATION.md](./INTEGRATION.md)

## Acknowledgments

Built with:
- Material-UI for components
- React for UI framework
- Vite for development experience
- TypeScript for type safety

Designed to match the clinical workflow and visual style of professional radiology software.
