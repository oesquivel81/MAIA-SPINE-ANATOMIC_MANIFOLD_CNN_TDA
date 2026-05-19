import { useState } from 'react';
import type { NormalizationResult } from './services/api';
import { Activity, Upload as UploadIcon, FileText } from 'lucide-react';
import { Button, Tabs, Tab, Box } from '@mui/material';
import { Toaster, toast } from 'sonner';
import { FileUpload } from './components/FileUpload';
import { ImageViewer } from './components/ImageViewer';
import { SpineDiagram } from './components/SpineDiagram';
import { MeasurementsTable } from './components/MeasurementsTable';
import { HeatmapVisualization } from './components/HeatmapVisualization';
import { apiService } from './services/api';

export default function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [normalizedImageUrl, setNormalizedImageUrl] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<NormalizationResult | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  const measurementData = analysisResult?.analysis?.measurements ?? [
    { parameter: 'Ángulo Cobb', value: 15.2, unit: '°', normalRange: '< 10°', status: 'warning' },
    { parameter: 'Inclinación pélvica', value: 8.5, unit: '°', normalRange: '5-10°', status: 'normal' },
    { parameter: 'Lordosis lumbar', value: 42.1, unit: '°', normalRange: '40-60°', status: 'normal' },
    { parameter: 'Cifosis torácica', value: 38.7, unit: '°', normalRange: '20-45°', status: 'normal' },
    { parameter: 'Desviación lateral', value: 12.3, unit: 'mm', normalRange: '< 5mm', status: 'critical' },
  ];

  const highlightedVertebrae = analysisResult?.analysis?.segmentation?.highlighted_vertebrae ?? [];
  const curveType = analysisResult?.analysis?.segmentation?.curve_type;
  const heatmapData = analysisResult?.analysis?.heatmap_data;
  const curveSummary = analysisResult?.analysis?.curve;
  const colorBands = analysisResult?.analysis?.color_index?.bands;

  const handleFileSelect = async (file: File) => {
    setSelectedFile(file);
    setNormalizedImageUrl(null);
  };

  const handleNormalizeImage = async () => {
    if (!selectedFile) {
      toast.error('Por favor selecciona una imagen primero');
      return;
    }

    setIsProcessing(true);
    try {
      const result = await apiService.normalizeImage(selectedFile);

      if (result.normalized_image_url) {
        setNormalizedImageUrl(result.normalized_image_url);
        setAnalysisResult(result);
        toast.success('Imagen normalizada exitosamente');
      } else {
        setAnalysisResult(result);
        toast.error('Error al normalizar la imagen: respuesta inválida del backend');
      }
    } catch (error) {
      console.error('Error normalizing image:', error);
      toast.error(error instanceof Error ? error.message : 'Error al procesar la imagen');
    } finally {
      setIsProcessing(false);
    }
  };

  const previewUrl = selectedFile ? URL.createObjectURL(selectedFile) : null;

  return (
    <>
      <Toaster position="top-right" richColors />
      <div className="size-full bg-[#0a0e1a] text-white overflow-auto">
      <div className="min-h-full p-6">
        <header className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-8 h-8 text-blue-500" />
            <h1 className="text-2xl">Diagnóstico de Escoliosis</h1>
          </div>
          <p className="text-sm text-gray-400">
            Sistema de análisis anatómico de columna vertebral con CNN y TDA
          </p>
        </header>

        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-3 space-y-4">
            <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
              <div className="flex items-center gap-2 mb-4">
                <UploadIcon className="w-5 h-5 text-blue-400" />
                <h2 className="text-sm">Carga de imagen</h2>
              </div>

              <FileUpload
                onFileSelect={handleFileSelect}
                accept="image/*"
                label="Radiografía de columna"
              />

              {selectedFile && (
                <div className="mt-4 space-y-2">
                  <Button
                    variant="contained"
                    fullWidth
                    onClick={handleNormalizeImage}
                    disabled={isProcessing}
                    startIcon={<Activity className="w-4 h-4" />}
                  >
                    {isProcessing ? 'Procesando...' : 'Analizar imagen'}
                  </Button>
                </div>
              )}
            </div>

            <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
              <div className="flex items-center gap-2 mb-4">
                <FileText className="w-5 h-5 text-blue-400" />
                <h2 className="text-sm">Opciones de análisis</h2>
              </div>

              <div className="space-y-3 text-sm">
                <label className="flex items-center gap-2">
                  <input type="checkbox" className="rounded" defaultChecked />
                  <span className="text-gray-300">Análisis automático</span>
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" className="rounded" defaultChecked />
                  <span className="text-gray-300">Mediciones Cobb</span>
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" className="rounded" />
                  <span className="text-gray-300">Comparar con perfil</span>
                </label>
              </div>
            </div>

            <SpineDiagram
              highlightedVertebrae={highlightedVertebrae}
              curveType={curveType}
            />
          </div>

          <div className="col-span-6">
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
              <Tabs
                value={activeTab}
                onChange={(_, newValue) => setActiveTab(newValue)}
                sx={{
                  '& .MuiTab-root': { color: '#9ca3af' },
                  '& .Mui-selected': { color: '#3b82f6' },
                }}
              >
                <Tab label="Imagen original" />
                <Tab label="Imagen procesada" />
                <Tab label="Método automático" />
              </Tabs>
            </Box>

            {activeTab === 0 && (
              <div className="grid grid-cols-2 gap-4">
                <ImageViewer
                  src={previewUrl || '/api/placeholder/400/500'}
                  alt="Vista frontal"
                  title="Imagen original"
                />
                <ImageViewer
                  src={previewUrl || '/api/placeholder/400/500'}
                  alt="Vista lateral"
                  title="Vista procesada"
                  showControls={false}
                />
              </div>
            )}

            {activeTab === 1 && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <ImageViewer
                    src={normalizedImageUrl || previewUrl || '/api/placeholder/400/500'}
                    alt="Imagen normalizada"
                    title="Normalización aplicada"
                  />
                  <ImageViewer
                    src={normalizedImageUrl || previewUrl || '/api/placeholder/400/500'}
                    alt="Análisis de curva"
                    title="Detección de curvaturas"
                    showControls={false}
                  />
                </div>

                {analysisResult && (
                  <div className="bg-gray-900 rounded-lg p-4 border border-gray-700 mt-4 text-sm">
                    <h3 className="text-sm text-gray-200 mb-3">Resultado del backend</h3>
                    <div className="grid grid-cols-2 gap-3 text-gray-300">
                      <div>
                        <div className="text-xs uppercase text-gray-500">Perfil seleccionado</div>
                        <div>{analysisResult.closest_profile_key}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase text-gray-500">Distancia</div>
                        <div>{analysisResult.closest_profile_distance.toFixed(3)}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase text-gray-500">Tamaño de salida</div>
                        <div>{analysisResult.output_shape.join(' × ')}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase text-gray-500">Fuente de perfil</div>
                        <div>{analysisResult.profile_source}</div>
                      </div>
                      {curveSummary ? (
                        <>
                          <div>
                            <div className="text-xs uppercase text-gray-500">Ángulo Cobb</div>
                            <div>{curveSummary.estimated_cobb_angle?.toFixed(1)}°</div>
                          </div>
                          <div>
                            <div className="text-xs uppercase text-gray-500">Dirección de curva</div>
                            <div>{curveSummary.direction}</div>
                          </div>
                          <div>
                            <div className="text-xs uppercase text-gray-500">Severidad</div>
                            <div>{curveSummary.severity}</div>
                          </div>
                          <div>
                            <div className="text-xs uppercase text-gray-500">Tramo principal</div>
                            <div>{curveType || 'N/A'}</div>
                          </div>
                        </>
                      ) : null}
                    </div>
                  </div>
                )}
              </>
            )}

            {activeTab === 2 && (
              <div className="bg-gray-900 rounded-lg p-6 border border-gray-700">
                <h3 className="text-lg mb-4">Método de análisis automático</h3>
                <div className="space-y-4 text-sm text-gray-300">
                  <p>
                    El sistema utiliza redes neuronales convolucionales (CNN) combinadas con
                    análisis topológico de datos (TDA) para identificar patrones anatómicos
                    en la columna vertebral.
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-800 rounded p-3">
                      <div className="text-blue-400 mb-1">Detección CNN</div>
                      <div className="text-xs text-gray-400">
                        Identificación automática de vértebras y puntos de referencia anatómicos
                      </div>
                    </div>
                    <div className="bg-gray-800 rounded p-3">
                      <div className="text-blue-400 mb-1">Análisis TDA</div>
                      <div className="text-xs text-gray-400">
                        Caracterización topológica de la estructura espinal
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="mt-4">
              <MeasurementsTable
                measurements={measurementData}
                title="Curvas / Segmentación / Origen"
              />
            </div>
          </div>

          <div className="col-span-3 space-y-4">
            <HeatmapVisualization data={heatmapData} />

            <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
              <h3 className="text-sm text-gray-200 mb-3">Índice de color</h3>
              <div className="space-y-2 text-xs">
                {colorBands?.length ? (
                  colorBands.map((band, index) => (
                    <div key={index} className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded" style={{ backgroundColor: band.color }} />
                      <span className="text-gray-400">{band.range} · {band.percentage}%</span>
                    </div>
                  ))
                ) : (
                  <>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-[#1e3a8a] rounded" />
                      <span className="text-gray-400">Rango bajo (0-20)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-[#3b82f6] rounded" />
                      <span className="text-gray-400">Rango medio-bajo (20-40)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-[#10b981] rounded" />
                      <span className="text-gray-400">Rango medio (40-60)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-[#fbbf24] rounded" />
                      <span className="text-gray-400">Rango medio-alto (60-80)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-[#ef4444] rounded" />
                      <span className="text-gray-400">Rango alto (80-100)</span>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
              <h3 className="text-sm text-gray-200 mb-3">Genera reporte (PDF)</h3>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<FileText className="w-4 h-4" />}
                disabled={!selectedFile}
              >
                Descargar reporte
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
    </>
  );
}