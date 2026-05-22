import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  ChevronRight,
  ClipboardList,
  Crosshair,
  Gauge,
  Layers3,
  RefreshCcw,
  RotateCcw,
  ScanLine,
  Sparkles,
  Waves,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { Button } from '@mui/material';
import {
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Toaster, toast } from 'sonner';
import type { AnalysisData, PatientInfo } from '../../types';
import { apiService } from './services/api';

type DashboardTab =
  | 'Resumen'
  | 'Imagen procesada'
  | 'Análisis estructural'
  | 'Detalle del punto';

type RegionName =
  | 'upper_thoracic_probable'
  | 'thoracic_probable'
  | 'thoracolumbar_probable'
  | 'lumbar_probable';

type MetricMode = 'gap_strength_mean' | 'peak_height' | 'cluster_probability' | 'cluster_entropy';

type PatientSummary = {
  patient: {
    name: string;
    sex: 'Hombre' | 'Mujer';
    age: number;
    weight: number;
  };
  summary: {
    cobb_angle: number;
    severity: 'mild' | 'moderate' | 'severe';
    n_gaps: number;
    n_regions: number;
    n_clusters: number;
    dominant_cluster_id: number;
    cluster_probability_mean: number;
    warning: string;
  };
};

type RegionCandidate = {
  peak_idx: number;
  curve_idx: number;
  t_norm: number;
  vertebra_id: number;
  anatomic_region_probable: RegionName;
  cluster_id: number;
  cluster_probability: number;
  cluster_entropy: number;
  gap_strength_mean: number;
  peak_height: number;
  peak_highpass_value: number;
  left_gap_strength: number;
  right_gap_strength: number;
  wavelength_prev: number;
  wavelength_next: number;
  kind: 'peak' | 'gap_peak';
  intervertebral_norm: number;
  boundary_norm: number;
  combined_signal: number;
  prominence: number;
};

type CurveBounds = {
  minCurveIdx: number;
  maxCurveIdx: number;
};

type CurvePoint = {
  x: number;
  y: number;
};

type SpineCurveRow = {
  curve_idx: number;
  x_curve: number;
  y_curve: number;
  t_norm: number;
};

type PeakCurveRow = {
  centroid_curve_x: number;
  centroid_curve_y: number;
  centroid_t_norm: number;
  spatial_order: number;
};

type ClusterSummary = {
  name: string;
  clusterId: number;
  regions: number;
  value: number;
  color: string;
};

type PatchInfo = {
  id: number;
  region: string;
  clusterId: number;
  intensity: number;
  src: string;
  curveIdx: number;
  peakIdx: number;
};

type DashboardImageSet = {
  normalizedImage?: string;
  processedImage?: string;
  structuralImage?: string;
  patchInputs: string[];
};

const colors = {
  page: '#07111f',
  card: '#0d1a2b',
  cardSoft: '#102033',
  border: '#1e324a',
  text: '#f8fafc',
  muted: '#94a3b8',
  active: '#2196f3',
  neon: '#38bdf8',
  green: '#22c55e',
  yellow: '#facc15',
  orange: '#f97316',
  red: '#ef4444',
  purple: '#9333ea',
  cyan: '#06b6d4',
};

const tabs: DashboardTab[] = [
  'Resumen',
  'Imagen procesada',
  'Análisis estructural',
  'Detalle del punto',
];

const patientSummary: PatientSummary = {
  patient: {
    name: 'Barba de algodon',
    sex: 'Hombre',
    age: 25,
    weight: 70,
  },
  summary: {
    cobb_angle: 19.88,
    severity: 'mild',
    n_gaps: 13,
    n_regions: 8,
    n_clusters: 5,
    dominant_cluster_id: 21,
    cluster_probability_mean: 0.9996,
    warning: 'Salida probabilística de investigación. No es un diagnóstico clínico.',
  },
};

const regionCandidates: RegionCandidate[] = [
  {
    peak_idx: 1,
    curve_idx: 72,
    t_norm: 0.071,
    vertebra_id: 7,
    anatomic_region_probable: 'upper_thoracic_probable',
    cluster_id: 21,
    cluster_probability: 0.9987,
    cluster_entropy: 0.081,
    gap_strength_mean: 0.24,
    peak_height: 0.28,
    peak_highpass_value: 0.22,
    left_gap_strength: 0.21,
    right_gap_strength: 0.29,
    wavelength_prev: 55,
    wavelength_next: 79,
    kind: 'peak',
    intervertebral_norm: 0.36,
    boundary_norm: 0.31,
    combined_signal: 0.42,
    prominence: 0.33,
  },
  {
    peak_idx: 2,
    curve_idx: 128,
    t_norm: 0.125,
    vertebra_id: 9,
    anatomic_region_probable: 'upper_thoracic_probable',
    cluster_id: 21,
    cluster_probability: 0.9991,
    cluster_entropy: 0.072,
    gap_strength_mean: 0.32,
    peak_height: 0.35,
    peak_highpass_value: 0.31,
    left_gap_strength: 0.27,
    right_gap_strength: 0.38,
    wavelength_prev: 61,
    wavelength_next: 68,
    kind: 'gap_peak',
    intervertebral_norm: 0.41,
    boundary_norm: 0.34,
    combined_signal: 0.48,
    prominence: 0.44,
  },
  {
    peak_idx: 3,
    curve_idx: 186,
    t_norm: 0.182,
    vertebra_id: 11,
    anatomic_region_probable: 'thoracic_probable',
    cluster_id: 22,
    cluster_probability: 0.9993,
    cluster_entropy: 0.066,
    gap_strength_mean: 0.44,
    peak_height: 0.49,
    peak_highpass_value: 0.45,
    left_gap_strength: 0.42,
    right_gap_strength: 0.48,
    wavelength_prev: 76,
    wavelength_next: 73,
    kind: 'peak',
    intervertebral_norm: 0.53,
    boundary_norm: 0.44,
    combined_signal: 0.59,
    prominence: 0.56,
  },
  {
    peak_idx: 4,
    curve_idx: 248,
    t_norm: 0.242,
    vertebra_id: 12,
    anatomic_region_probable: 'thoracic_probable',
    cluster_id: 22,
    cluster_probability: 0.9995,
    cluster_entropy: 0.054,
    gap_strength_mean: 0.51,
    peak_height: 0.58,
    peak_highpass_value: 0.56,
    left_gap_strength: 0.47,
    right_gap_strength: 0.59,
    wavelength_prev: 81,
    wavelength_next: 70,
    kind: 'gap_peak',
    intervertebral_norm: 0.61,
    boundary_norm: 0.52,
    combined_signal: 0.67,
    prominence: 0.65,
  },
  {
    peak_idx: 5,
    curve_idx: 312,
    t_norm: 0.305,
    vertebra_id: 14,
    anatomic_region_probable: 'thoracic_probable',
    cluster_id: 11,
    cluster_probability: 0.9996,
    cluster_entropy: 0.048,
    gap_strength_mean: 0.57,
    peak_height: 0.61,
    peak_highpass_value: 0.6,
    left_gap_strength: 0.52,
    right_gap_strength: 0.63,
    wavelength_prev: 88,
    wavelength_next: 63,
    kind: 'peak',
    intervertebral_norm: 0.66,
    boundary_norm: 0.58,
    combined_signal: 0.72,
    prominence: 0.69,
  },
  {
    peak_idx: 6,
    curve_idx: 388,
    t_norm: 0.379,
    vertebra_id: 16,
    anatomic_region_probable: 'thoracic_probable',
    cluster_id: 11,
    cluster_probability: 0.9997,
    cluster_entropy: 0.042,
    gap_strength_mean: 0.63,
    peak_height: 0.67,
    peak_highpass_value: 0.66,
    left_gap_strength: 0.59,
    right_gap_strength: 0.69,
    wavelength_prev: 94,
    wavelength_next: 58,
    kind: 'gap_peak',
    intervertebral_norm: 0.72,
    boundary_norm: 0.63,
    combined_signal: 0.79,
    prominence: 0.76,
  },
  {
    peak_idx: 7,
    curve_idx: 452,
    t_norm: 0.441,
    vertebra_id: 18,
    anatomic_region_probable: 'thoracolumbar_probable',
    cluster_id: 21,
    cluster_probability: 0.9998,
    cluster_entropy: 0.035,
    gap_strength_mean: 0.7,
    peak_height: 0.74,
    peak_highpass_value: 0.73,
    left_gap_strength: 0.67,
    right_gap_strength: 0.74,
    wavelength_prev: 101,
    wavelength_next: 52,
    kind: 'peak',
    intervertebral_norm: 0.77,
    boundary_norm: 0.69,
    combined_signal: 0.85,
    prominence: 0.81,
  },
  {
    peak_idx: 8,
    curve_idx: 518,
    t_norm: 0.506,
    vertebra_id: 20,
    anatomic_region_probable: 'thoracolumbar_probable',
    cluster_id: 18,
    cluster_probability: 0.9998,
    cluster_entropy: 0.031,
    gap_strength_mean: 0.76,
    peak_height: 0.83,
    peak_highpass_value: 0.81,
    left_gap_strength: 0.73,
    right_gap_strength: 0.79,
    wavelength_prev: 95,
    wavelength_next: 40,
    kind: 'gap_peak',
    intervertebral_norm: 0.81,
    boundary_norm: 0.74,
    combined_signal: 0.91,
    prominence: 0.88,
  },
  {
    peak_idx: 9,
    curve_idx: 604,
    t_norm: 0.59,
    vertebra_id: 21,
    anatomic_region_probable: 'thoracolumbar_probable',
    cluster_id: 22,
    cluster_probability: 0.9999,
    cluster_entropy: 0.026,
    gap_strength_mean: 0.82,
    peak_height: 0.9,
    peak_highpass_value: 0.88,
    left_gap_strength: 0.8,
    right_gap_strength: 0.86,
    wavelength_prev: 90,
    wavelength_next: 28,
    kind: 'peak',
    intervertebral_norm: 0.87,
    boundary_norm: 0.81,
    combined_signal: 0.99,
    prominence: 0.93,
  },
  {
    peak_idx: 10,
    curve_idx: 690,
    t_norm: 0.674,
    vertebra_id: 23,
    anatomic_region_probable: 'thoracolumbar_probable',
    cluster_id: 22,
    cluster_probability: 1,
    cluster_entropy: 0.019,
    gap_strength_mean: 0.988,
    peak_height: 1,
    peak_highpass_value: 0.97,
    left_gap_strength: 0.96,
    right_gap_strength: 0.99,
    wavelength_prev: 85,
    wavelength_next: 1,
    kind: 'gap_peak',
    intervertebral_norm: 0.93,
    boundary_norm: 0.9,
    combined_signal: 1.08,
    prominence: 1,
  },
  {
    peak_idx: 11,
    curve_idx: 756,
    t_norm: 0.738,
    vertebra_id: 24,
    anatomic_region_probable: 'lumbar_probable',
    cluster_id: 11,
    cluster_probability: 0.9999,
    cluster_entropy: 0.022,
    gap_strength_mean: 0.84,
    peak_height: 0.88,
    peak_highpass_value: 0.86,
    left_gap_strength: 0.82,
    right_gap_strength: 0.89,
    wavelength_prev: 77,
    wavelength_next: 19,
    kind: 'peak',
    intervertebral_norm: 0.89,
    boundary_norm: 0.85,
    combined_signal: 0.97,
    prominence: 0.91,
  },
  {
    peak_idx: 12,
    curve_idx: 828,
    t_norm: 0.809,
    vertebra_id: 25,
    anatomic_region_probable: 'lumbar_probable',
    cluster_id: 11,
    cluster_probability: 0.9998,
    cluster_entropy: 0.027,
    gap_strength_mean: 0.69,
    peak_height: 0.74,
    peak_highpass_value: 0.71,
    left_gap_strength: 0.66,
    right_gap_strength: 0.73,
    wavelength_prev: 69,
    wavelength_next: 33,
    kind: 'gap_peak',
    intervertebral_norm: 0.78,
    boundary_norm: 0.72,
    combined_signal: 0.83,
    prominence: 0.79,
  },
  {
    peak_idx: 13,
    curve_idx: 904,
    t_norm: 0.883,
    vertebra_id: 26,
    anatomic_region_probable: 'lumbar_probable',
    cluster_id: 2,
    cluster_probability: 0.9994,
    cluster_entropy: 0.041,
    gap_strength_mean: 0.52,
    peak_height: 0.57,
    peak_highpass_value: 0.54,
    left_gap_strength: 0.5,
    right_gap_strength: 0.56,
    wavelength_prev: 60,
    wavelength_next: 48,
    kind: 'peak',
    intervertebral_norm: 0.61,
    boundary_norm: 0.55,
    combined_signal: 0.68,
    prominence: 0.61,
  },
  {
    peak_idx: 14,
    curve_idx: 972,
    t_norm: 0.949,
    vertebra_id: 27,
    anatomic_region_probable: 'lumbar_probable',
    cluster_id: 21,
    cluster_probability: 0.9991,
    cluster_entropy: 0.049,
    gap_strength_mean: 0.39,
    peak_height: 0.43,
    peak_highpass_value: 0.41,
    left_gap_strength: 0.34,
    right_gap_strength: 0.45,
    wavelength_prev: 48,
    wavelength_next: 60,
    kind: 'gap_peak',
    intervertebral_norm: 0.49,
    boundary_norm: 0.42,
    combined_signal: 0.53,
    prominence: 0.46,
  },
];

const clusterSummary: ClusterSummary[] = [
  { name: 'Cluster 21', clusterId: 21, regions: 4, value: 28.6, color: '#2196f3' },
  { name: 'Cluster 22', clusterId: 22, regions: 3, value: 21.4, color: '#22c55e' },
  { name: 'Cluster 11', clusterId: 11, regions: 4, value: 28.6, color: '#facc15' },
  { name: 'Cluster 18', clusterId: 18, regions: 1, value: 7.1, color: '#f97316' },
  { name: 'Cluster 2', clusterId: 2, regions: 1, value: 7.1, color: '#9333ea' },
];

const metricSparklines = {
  gap: [0.21, 0.24, 0.36, 0.42, 0.53, 0.61, 0.7, 0.88],
  peak: [0.31, 0.34, 0.4, 0.46, 0.56, 0.65, 0.74, 0.83],
  probability: [0.996, 0.997, 0.998, 0.9987, 0.999, 0.9993, 0.9996, 0.9996],
};

const mockImages = {
  normalized_image: buildPanelImage('Radiografía normalizada', 'Contraste clínico homogéneo', '#2196f3'),
  analysis_grid: buildAnalysisGridImage(),
  gap_peak_analysis: buildPanelImage('Gaps + Peaks', 'Señal dinámica en curva', '#ef4444', true),
  spatial_index_panel: buildPanelImage('Spatial index panel', 'Curva, centroides y peaks', '#22c55e', true),
  patch_inputs: Array.from({ length: 8 }, (_, index) => buildPatchImage(index + 1)),
};

function severityLabel(value?: string) {
  if (!value) {
    return 'Pendiente';
  }

  const normalized = value.trim().toLowerCase();
  if (normalized === 'mild') {
    return 'Leve';
  }
  if (normalized === 'moderate') {
    return 'Moderada';
  }
  if (normalized === 'severe') {
    return 'Severa';
  }

  return value;
}

function buildWarning(data?: AnalysisData) {
  if (!data) {
    return patientSummary.summary.warning;
  }

  const severity = data.predictions.cobb_severity?.toLowerCase();
  if (severity === 'severe') {
    return 'Escoliosis severa detectada. Requiere revisión clínica prioritaria.';
  }
  if (severity === 'moderate') {
    return 'Escoliosis moderada detectada. Validar progresión y seguimiento radiográfico.';
  }

  return 'Respuesta del pipeline cargada desde el backend. Validar hallazgos con criterio clínico.';
}

function buildDashboardSummary(data?: AnalysisData): PatientSummary['summary'] {
  if (!data) {
    return patientSummary.summary;
  }

  const clusterProbabilityMean = regionCandidates.reduce((total, candidate) => total + candidate.cluster_probability, 0) / regionCandidates.length;

  return {
    cobb_angle: data.predictions.cobb_angle_deg ?? patientSummary.summary.cobb_angle,
    severity: ((data.predictions.cobb_severity?.toLowerCase() as PatientSummary['summary']['severity']) || patientSummary.summary.severity),
    n_gaps: data.gap_summary.n_gap_peaks ?? patientSummary.summary.n_gaps,
    n_regions: data.images.patch_inputs?.length ?? patientSummary.summary.n_regions,
    n_clusters: data.predictions.n_clusters_detected ?? patientSummary.summary.n_clusters,
    dominant_cluster_id: data.predictions.dominant_cluster_id ?? patientSummary.summary.dominant_cluster_id,
    cluster_probability_mean: Number.isFinite(clusterProbabilityMean) ? clusterProbabilityMean : patientSummary.summary.cluster_probability_mean,
    warning: buildWarning(data),
  };
}

function buildDashboardImages(data?: AnalysisData): DashboardImageSet {
  if (data) {
    return {
      normalizedImage: data.images.normalized_image,
      processedImage: data.images.analysis_grid,
      structuralImage: data.images.spatial_index_panel || data.images.gap_peak_analysis,
      patchInputs: data.images.patch_inputs?.length ? data.images.patch_inputs : [],
    };
  }

  return {
    normalizedImage: mockImages.normalized_image,
    processedImage: mockImages.spatial_index_panel,
    structuralImage: mockImages.analysis_grid,
    patchInputs: mockImages.patch_inputs,
  };
}

function buildClusterSummary(candidates: RegionCandidate[], detectedClusters?: number): ClusterSummary[] {
  const counts = new Map<number, number>();
  candidates.forEach((candidate) => {
    counts.set(candidate.cluster_id, (counts.get(candidate.cluster_id) ?? 0) + 1);
  });

  const base = Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1])
    .map(([clusterId, regions]) => ({
      name: `Cluster ${clusterId}`,
      clusterId,
      regions,
      value: Number(((regions / candidates.length) * 100).toFixed(1)),
      color: clusterColor(clusterId),
    }));

  if (base.length > 0) {
    return base;
  }

  return clusterSummary.slice(0, detectedClusters ?? clusterSummary.length);
}

function buildPatientPayload(patient: PatientSummary['patient']): PatientInfo {
  const trimmedName = patient.name.trim();
  const [nombre, ...rest] = trimmedName.split(/\s+/).filter(Boolean);
  return {
    nombre: nombre || 'Paciente',
    apellido_paterno: rest.join(' ') || 'Sin apellido',
    edad: patient.age,
    peso: patient.weight,
    sexo: patient.sex,
    fecha: new Date().toISOString().slice(0, 10),
  };
}

export default function App() {
  const [activeTab, setActiveTab] = useState<DashboardTab>('Resumen');
  const [patientForm, setPatientForm] = useState(patientSummary.patient);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [selectedPeakIdx, setSelectedPeakIdx] = useState(10);
  const [sliderValue, setSliderValue] = useState(690);
  const [heatMetric, setHeatMetric] = useState<MetricMode>('gap_strength_mean');
  const [clusterFilter, setClusterFilter] = useState<'all' | number>('all');
  const [regionFilter, setRegionFilter] = useState<'all' | RegionName>('all');
  const [heatRotation, setHeatRotation] = useState(18);
  const [heatZoom, setHeatZoom] = useState(1);
  const [liveRegionCandidates, setLiveRegionCandidates] = useState<RegionCandidate[] | null>(null);
  const [spineRealCurve, setSpineRealCurve] = useState<SpineCurveRow[] | null>(null);
  const [spinePeaksCurve, setSpinePeaksCurve] = useState<PeakCurveRow[] | null>(null);

  const summary = useMemo(() => buildDashboardSummary(analysisData ?? undefined), [analysisData]);
  const dashboardImages = useMemo(() => buildDashboardImages(analysisData ?? undefined), [analysisData]);

  // Candidatos activos: real del backend si disponibles, si no mock
  const activeCandidates = useMemo(
    () => liveRegionCandidates ?? regionCandidates,
    [liveRegionCandidates],
  );

  const dashboardClusters = useMemo(
    () => buildClusterSummary(activeCandidates, analysisData?.predictions.n_clusters_detected),
    [activeCandidates, analysisData?.predictions.n_clusters_detected],
  );

  useEffect(() => {
    if (!analysisData?.patient_name) {
      return;
    }

    setPatientForm((current) => ({
      ...current,
      name: analysisData.patient_name,
    }));
  }, [analysisData]);

  // Cargar clinical_regions.csv → RegionCandidate[] reales
  useEffect(() => {
    const url = analysisData?.predictions.regions_csv_path;
    if (!url) {
      setLiveRegionCandidates(null);
      return;
    }
    let cancelled = false;
    fetch(url)
      .then((r) => r.text())
      .then((text) => {
        if (!cancelled) {
          const rows = parseRegionsCSV(text);
          if (rows.length > 0) setLiveRegionCandidates(rows);
        }
      })
      .catch(() => { if (!cancelled) setLiveRegionCandidates(null); });
    return () => { cancelled = true; };
  }, [analysisData?.predictions.regions_csv_path]);

  // Cargar curve_spatial_index.csv → SpineCurveRow[] reales
  useEffect(() => {
    const url = analysisData?.nerve_curve?.curve_csv_path;
    if (!url) {
      setSpineRealCurve(null);
      return;
    }
    let cancelled = false;
    fetch(url)
      .then((r) => r.text())
      .then((text) => {
        if (!cancelled) {
          const rows = parseCurveCSV(text);
          if (rows.length > 0) setSpineRealCurve(rows);
        }
      })
      .catch(() => { if (!cancelled) setSpineRealCurve(null); });
    return () => { cancelled = true; };
  }, [analysisData?.nerve_curve?.curve_csv_path]);

  // Cargar centroid_peak_spatial_index.csv → PeakCurveRow[] para overlay imagen
  useEffect(() => {
    const url = analysisData?.nerve_curve?.peaks_csv_path;
    if (!url) {
      setSpinePeaksCurve(null);
      return;
    }
    let cancelled = false;
    fetch(url)
      .then((r) => r.text())
      .then((text) => {
        if (!cancelled) {
          const rows = parsePeaksCSV(text);
          if (rows.length > 0) setSpinePeaksCurve(rows);
        }
      })
      .catch(() => { if (!cancelled) setSpinePeaksCurve(null); });
    return () => { cancelled = true; };
  }, [analysisData?.nerve_curve?.peaks_csv_path]);

  const filteredCandidates = useMemo(() => {
    return activeCandidates.filter((candidate) => {
      const clusterOk = clusterFilter === 'all' || candidate.cluster_id === clusterFilter;
      const regionOk = regionFilter === 'all' || candidate.anatomic_region_probable === regionFilter;
      return clusterOk && regionOk;
    });
  }, [activeCandidates, clusterFilter, regionFilter]);

  const orderedCandidates = useMemo(() => {
    return [...filteredCandidates].sort((left, right) => {
      if (left.curve_idx !== right.curve_idx) {
        return left.curve_idx - right.curve_idx;
      }

      return left.peak_idx - right.peak_idx;
    });
  }, [filteredCandidates]);

  const curveBounds = useMemo(() => {
    return curveBoundsFromCandidates(orderedCandidates);
  }, [orderedCandidates]);

  const selectedCandidate = useMemo(() => {
    return (
      orderedCandidates.find((candidate) => candidate.peak_idx === selectedPeakIdx) ??
      orderedCandidates[0] ??
      activeCandidates[0] ??
      regionCandidates[0]
    );
  }, [orderedCandidates, selectedPeakIdx, activeCandidates]);

  const selectedCurvePoint = useMemo(() => {
    if (spineRealCurve) return curvePointFromRealData(selectedCandidate.curve_idx, spineRealCurve);
    return curvePointForCandidate(selectedCandidate, curveBounds);
  }, [curveBounds, selectedCandidate, spineRealCurve]);

  const selectedClusterSummary = useMemo(() => {
    return dashboardClusters.find((entry) => entry.clusterId === selectedCandidate.cluster_id);
  }, [dashboardClusters, selectedCandidate.cluster_id]);

  const patchCards: PatchInfo[] = useMemo(() => {
    return dashboardImages.patchInputs.map((src, index) => {
      const candidate = activeCandidates[index];
      return {
        id: index + 1,
        region: candidate ? readableRegion(candidate.anatomic_region_probable) : `Orden anatómico ${index + 1}`,
        clusterId: candidate?.cluster_id ?? analysisData?.predictions.dominant_cluster_id ?? 0,
        intensity: candidate?.gap_strength_mean ?? 0,
        curveIdx: candidate?.curve_idx ?? index,
        peakIdx: candidate?.peak_idx ?? -1,
        src,
      };
    });
  }, [analysisData?.predictions.dominant_cluster_id, dashboardImages.patchInputs, activeCandidates]);

  const positionOrderedPatches = useMemo(() => {
    return [...patchCards].sort((a, b) => a.curveIdx - b.curveIdx);
  }, [patchCards]);

  const handleSelectCandidate = (candidate: RegionCandidate) => {
    setSelectedPeakIdx(candidate.peak_idx);
    setSliderValue(candidate.curve_idx);
  };

  const handleSliderChange = (value: number) => {
    setSliderValue(value);
    const nearest = orderedCandidates.reduce((closest, candidate) => {
      return Math.abs(candidate.curve_idx - value) < Math.abs(closest.curve_idx - value) ? candidate : closest;
    }, orderedCandidates[0] ?? activeCandidates[0] ?? regionCandidates[0]);
    handleSelectCandidate(nearest);
  };

  const resetHeatmap = () => {
    setHeatRotation(18);
    setHeatZoom(1);
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      toast.error('Selecciona una radiografía antes de ejecutar el análisis');
      return;
    }

    setIsAnalyzing(true);

    try {
      const result = await apiService.analyzeSpine(selectedFile, buildPatientPayload(patientForm));
      setAnalysisData(result);
      setActiveTab('Resumen');
      setClusterFilter('all');
      setRegionFilter('all');
      setHeatMetric('gap_strength_mean');
      handleSelectCandidate(activeCandidates[0] ?? regionCandidates[0]);
      resetHeatmap();
      toast.success('Análisis cargado desde el backend');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'No se pudo ejecutar el análisis';
      toast.error(message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleNewAnalysis = () => {
    setAnalysisData(null);
    setSelectedFile(null);
    setActiveTab('Resumen');
    setClusterFilter('all');
    setRegionFilter('all');
    setHeatMetric('gap_strength_mean');
    setLiveRegionCandidates(null);
    setSpineRealCurve(null);
    setSpinePeaksCurve(null);
    handleSelectCandidate(regionCandidates[9]);
    resetHeatmap();
    toast.success('Dashboard reiniciado para un nuevo análisis');
  };

  return (
    <>
      <Toaster position="top-right" richColors />
      <div className="min-h-screen overflow-x-hidden bg-[#07111f] text-slate-50">
        <div className="mx-auto flex min-h-screen max-w-[1680px] flex-col px-4 py-4 xl:px-6">
          <PatientHeader
            patient={patientForm}
            selectedFileName={selectedFile?.name ?? null}
            requestId={analysisData?.request_id}
            isAnalyzing={isAnalyzing}
            onPatientChange={setPatientForm}
            onFileSelect={setSelectedFile}
            onAnalyze={handleAnalyze}
            onNewAnalysis={handleNewAnalysis}
          />

          <DashboardTabs activeTab={activeTab} onChange={setActiveTab} />

          <main className="mt-4 min-h-0 flex-1 overflow-x-hidden pb-2">
            {activeTab === 'Resumen' && (
              <div className="grid h-full min-h-0 grid-cols-12 gap-4">
                <div className="col-span-12 min-h-0 overflow-hidden xl:col-span-3">
                  <SummarySidebar summary={summary} clusters={dashboardClusters} />
                </div>

                <div className="col-span-12 min-h-0 overflow-hidden xl:col-span-6">
                  <div className="grid gap-4">
                    <StructuralAnalysisPanel
                      imageSrc={dashboardImages.structuralImage}
                      normalizedImageSrc={dashboardImages.normalizedImage}
                      peaksCurve={spinePeaksCurve ?? undefined}
                    />
                    <DynamicCurveSection
                      candidates={orderedCandidates}
                      selectedCandidate={selectedCandidate}
                      selectedCurvePoint={selectedCurvePoint}
                      sliderValue={sliderValue}
                      onSliderChange={handleSliderChange}
                      onSelectCandidate={handleSelectCandidate}
                      realCurve={spineRealCurve ?? undefined}
                    />
                  </div>
                </div>

                <div className="col-span-12 min-h-0 overflow-hidden xl:col-span-3">
                  <PatchColumn
                    patches={positionOrderedPatches}
                    selectedPeakIdx={selectedCandidate.peak_idx}
                    onSelectPatch={(pk) => {
                      const c = orderedCandidates.find((x) => x.peak_idx === pk);
                      if (c) handleSelectCandidate(c);
                    }}
                  />
                </div>
              </div>
            )}

            {activeTab === 'Imagen procesada' && (
              <ProcessedImageTab
                imageSrc={dashboardImages.processedImage}
                summary={summary}
                selectedCandidate={selectedCandidate}
              />
            )}

            {activeTab === 'Análisis estructural' && (
              <StructuralAnalysisStandalone imageSrc={dashboardImages.structuralImage} />
            )}

            {activeTab === 'Detalle del punto' && (
              <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
                <SelectedPointDetailPanel
                  candidate={selectedCandidate}
                  clusterName={selectedClusterSummary?.name ?? `Cluster ${selectedCandidate.cluster_id}`}
                />
                <RegionCandidateTable
                  candidates={orderedCandidates}
                  selectedPeakIdx={selectedCandidate.peak_idx}
                  onSelectCandidate={handleSelectCandidate}
                />
              </div>
            )}

          </main>
        </div>
      </div>
    </>
  );
}

function PatientHeader({
  patient,
  selectedFileName,
  requestId,
  isAnalyzing,
  onPatientChange,
  onFileSelect,
  onAnalyze,
  onNewAnalysis,
}: {
  patient: PatientSummary['patient'];
  selectedFileName: string | null;
  requestId?: string;
  isAnalyzing: boolean;
  onPatientChange: (patient: PatientSummary['patient']) => void;
  onFileSelect: (file: File | null) => void;
  onAnalyze: () => void;
  onNewAnalysis: () => void;
}) {
  return (
    <section className="rounded-[28px] border border-[#1e324a] bg-[#0d1a2b]/95 px-6 py-5 shadow-[0_24px_80px_rgba(0,0,0,0.32)]">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-sky-500/30 bg-sky-500/10 shadow-[0_0_28px_rgba(33,150,243,0.25)]">
            <Activity className="h-7 w-7 text-sky-400" />
          </div>
          <div>
            <h1 className="text-[2rem] font-semibold tracking-tight text-slate-50">Diagnóstico de Escoliosis</h1>
            <p className="mt-1 text-sm text-slate-400">
              Sistema de análisis anatómico de columna vertebral con CNN y TDA
            </p>
          </div>
        </div>

        <div className="grid flex-1 grid-cols-1 gap-3 md:grid-cols-2 xl:mx-6 xl:max-w-[760px] xl:grid-cols-4">
          <HeaderField
            label="Nombre"
            value={patient.name}
            onChange={(value) => onPatientChange({ ...patient, name: value })}
          />
          <HeaderSelect
            label="Sexo"
            value={patient.sex}
            options={['Hombre', 'Mujer']}
            onChange={(value) => onPatientChange({ ...patient, sex: value as 'Hombre' | 'Mujer' })}
          />
          <HeaderField
            label="Edad"
            value={`${patient.age}`}
            onChange={(value) => onPatientChange({ ...patient, age: Number(value || 0) })}
          />
          <HeaderField
            label="Peso (kg)"
            value={`${patient.weight}`}
            onChange={(value) => onPatientChange({ ...patient, weight: Number(value || 0) })}
          />
        </div>

        <div className="flex items-center gap-3">
          <label className="rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-3 text-sm text-slate-300">
            <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">Radiografía</span>
            <input
              type="file"
              accept="image/*"
              className="mt-2 block max-w-[220px] text-xs text-slate-300 file:mr-3 file:rounded-xl file:border-0 file:bg-sky-500/15 file:px-3 file:py-2 file:text-xs file:font-medium file:text-sky-200"
              onChange={(event) => onFileSelect(event.target.files?.[0] ?? null)}
            />
            <span className="mt-2 block truncate text-xs text-slate-500">{selectedFileName ?? 'Sin archivo seleccionado'}</span>
          </label>
          <Button
            variant="outlined"
            onClick={onAnalyze}
            disabled={isAnalyzing}
            sx={{
              borderRadius: '16px',
              borderColor: 'rgba(56, 189, 248, 0.35)',
              color: '#e0f2fe',
              paddingX: '18px',
              paddingY: '10px',
              textTransform: 'none',
              fontWeight: 600,
            }}
          >
            {isAnalyzing ? 'Analizando...' : 'Ejecutar análisis'}
          </Button>
          <Button
            variant="contained"
            onClick={onNewAnalysis}
            sx={{
              borderRadius: '16px',
              backgroundColor: colors.active,
              paddingX: '18px',
              paddingY: '10px',
              boxShadow: '0 0 26px rgba(33,150,243,0.28)',
              textTransform: 'none',
              fontWeight: 600,
            }}
          >
            Nuevo análisis
          </Button>
        </div>
      </div>
      {requestId && <div className="mt-4 text-xs uppercase tracking-[0.18em] text-slate-500">request_id: {requestId}</div>}
    </section>
  );
}

function HeaderField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-2 rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-3 text-sm">
      <span className="text-xs uppercase tracking-[0.22em] text-slate-500">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
      />
    </label>
  );
}

function HeaderSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-2 rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-3 text-sm">
      <span className="text-xs uppercase tracking-[0.22em] text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="bg-transparent text-sm text-slate-100 outline-none"
      >
        {options.map((option) => (
          <option key={option} value={option} className="bg-[#102033]">
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function DashboardTabs({
  activeTab,
  onChange,
}: {
  activeTab: DashboardTab;
  onChange: (tab: DashboardTab) => void;
}) {
  return (
    <div className="mt-4 rounded-2xl border border-[#1e324a] bg-[#0b1727] p-2">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-4">
        {tabs.map((tab) => {
          const isActive = tab === activeTab;
          const label = tab;
          return (
            <button
              key={tab}
              onClick={() => onChange(tab)}
              className={`relative rounded-xl px-2 py-2 text-center text-xs font-medium transition-colors lg:px-3 lg:text-sm ${
                isActive ? 'text-slate-50' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {label}
              <span
                className={`absolute bottom-0 left-3 right-3 h-[3px] rounded-full bg-[#2196f3] transition-opacity ${
                  isActive ? 'opacity-100' : 'opacity-0'
                }`}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SummarySidebar({ summary, clusters }: { summary: PatientSummary['summary']; clusters: ClusterSummary[] }) {
  return (
    <div className="grid h-full gap-4 overflow-hidden">
      <SectionCard
        title="Resumen del análisis"
        icon={<ClipboardList className="h-4 w-4 text-sky-400" />}
      >
        <div className="grid gap-3">
          <MetricRow label="Cobb probabilístico" value={`${summary.cobb_angle.toFixed(2)}°`} accent={colors.active} />
          <MetricRow label="Severidad" value={severityLabel(summary.severity)} accent={colors.green} />
          <MetricRow label="Gaps probables" value={`${summary.n_gaps}`} accent={colors.yellow} />
          <MetricRow label="Regiones vertebrales probables" value={`${summary.n_regions}`} accent={colors.neon} />
          <MetricRow label="Clusters detectados" value={`${summary.n_clusters}`} accent={colors.orange} />
          <MetricRow label="Cluster dominante" value={`${summary.dominant_cluster_id}`} accent={colors.purple} />
          <MetricRow
            label="Probabilidad media clusters"
            value={summary.cluster_probability_mean.toFixed(4)}
            accent={colors.green}
          />
          <MetricRow label="Método Cobb" value="Probabilístico (curva)" accent={colors.active} />
        </div>
        <div className="mt-4 rounded-2xl border border-orange-500/30 bg-orange-500/10 px-4 py-3 text-sm text-orange-200">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{summary.warning}</span>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="Distribución de clusters"
        icon={<Layers3 className="h-4 w-4 text-sky-400" />}
      >
        <div className="h-56">
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={clusters}
                dataKey="value"
                nameKey="name"
                innerRadius={58}
                outerRadius={82}
                paddingAngle={4}
              >
                {clusters.map((entry) => (
                  <Cell key={entry.clusterId} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number, _name, payload) => [`${value}%`, payload?.payload?.name]}
                contentStyle={tooltipStyle}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="grid gap-2 text-sm text-slate-300">
          {clusters.map((entry) => (
            <div key={entry.clusterId} className="flex items-center justify-between rounded-xl bg-[#102033] px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                <span>{entry.name}</span>
              </div>
              <span className="text-slate-400">
                {entry.regions} regiones, {entry.value}%
              </span>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        title="Métricas globales promedio"
        icon={<Gauge className="h-4 w-4 text-sky-400" />}
      >
        <MetricSparkline label="Gap strength media" value="0.53" data={metricSparklines.gap} color={colors.cyan} />
        <MetricSparkline label="Peak height media" value="0.56" data={metricSparklines.peak} color={colors.yellow} />
        <MetricSparkline
          label="Probabilidad media"
          value={summary.cluster_probability_mean.toFixed(4)}
          data={metricSparklines.probability}
          color={colors.green}
        />
      </SectionCard>
    </div>
  );
}

function StructuralAnalysisPanel({
  imageSrc,
  normalizedImageSrc,
  peaksCurve,
}: {
  imageSrc: string;
  normalizedImageSrc?: string;
  peaksCurve?: PeakCurveRow[];
}) {
  const overlayCurvePath = useMemo(() => {
    if (!peaksCurve || peaksCurve.length === 0) return '';
    const sorted = [...peaksCurve].sort((a, b) => a.spatial_order - b.spatial_order);
    const xs = sorted.map((r) => r.centroid_curve_x);
    const ys = sorted.map((r) => r.centroid_curve_y);
    const xMin = Math.min(...xs); const xMax = Math.max(...xs);
    const yMin = Math.min(...ys); const yMax = Math.max(...ys);
    const xRange = Math.max(xMax - xMin, 1);
    const yRange = Math.max(yMax - yMin, 1);
    return sorted
      .map((row, i) => {
        const x = ((row.centroid_curve_x - xMin) / xRange) * 100;
        const y = ((row.centroid_curve_y - yMin) / yRange) * 100;
        return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
      })
      .join(' ');
  }, [peaksCurve]);

  return (
    <SectionCard
      title="Análisis estructural — imagen normalizada + curva"
      icon={<ScanLine className="h-4 w-4 text-sky-400" />}
      className="overflow-hidden"
    >
      <div className="grid gap-3 md:grid-cols-2">
        {/* Imagen original normalizada */}
        <div className="overflow-hidden rounded-2xl border border-[#1e324a] bg-[#08111d]">
          <div className="mb-1 px-2 pt-2 text-xs text-slate-500 uppercase tracking-widest">Original normalizada</div>
          <img src={normalizedImageSrc || imageSrc} alt="Imagen normalizada" className="h-[clamp(260px,40vh,520px)] w-full object-contain bg-[#07111f]" />
        </div>
        {/* Imagen + overlay de curva */}
        <div className="overflow-hidden rounded-2xl border border-[#1e324a] bg-[#08111d]">
          <div className="mb-1 px-2 pt-2 text-xs text-slate-500 uppercase tracking-widest">Overlay curva anatómica</div>
          <div className="relative h-[clamp(170px,26vh,240px)] bg-[#07111f]">
            <img
              src={normalizedImageSrc || imageSrc}
              alt="Overlay"
              className="absolute inset-0 h-full w-full object-contain"
            />
            {overlayCurvePath && (
              <svg
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                className="absolute inset-0 h-full w-full"
              >
                <path
                  d={overlayCurvePath}
                  fill="none"
                  stroke="#2196f3"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity="0.9"
                />
                {peaksCurve &&
                  [...peaksCurve].sort((a, b) => a.spatial_order - b.spatial_order).map((row, i) => {
                    const xs = peaksCurve.map((r) => r.centroid_curve_x);
                    const ys = peaksCurve.map((r) => r.centroid_curve_y);
                    const xMin = Math.min(...xs); const xMax = Math.max(...xs);
                    const yMin = Math.min(...ys); const yMax = Math.max(...ys);
                    const x = ((row.centroid_curve_x - xMin) / Math.max(xMax - xMin, 1)) * 100;
                    const y = ((row.centroid_curve_y - yMin) / Math.max(yMax - yMin, 1)) * 100;
                    return <circle key={i} cx={x} cy={y} r="1.2" fill="#22c55e" opacity="0.9" />;
                  })}
              </svg>
            )}
            {!overlayCurvePath && (
              <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-500">
                Curva disponible tras análisis
              </div>
            )}
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

function DynamicCurveSection({
  candidates,
  selectedCandidate,
  selectedCurvePoint,
  sliderValue,
  onSliderChange,
  onSelectCandidate,
  realCurve,
}: {
  candidates: RegionCandidate[];
  selectedCandidate: RegionCandidate;
  selectedCurvePoint: { x: number; y: number };
  sliderValue: number;
  onSliderChange: (value: number) => void;
  onSelectCandidate: (candidate: RegionCandidate) => void;
  realCurve?: SpineCurveRow[];
}) {
  return (
    <SectionCard
      title="Análisis dinámico de la curva + gaps (peaks)"
      icon={<BrainCircuit className="h-4 w-4 text-sky-400" />}
    >
      <div className="grid gap-4 xl:grid-cols-[1.05fr_1.15fr]">
        <DynamicCurveViewer
          candidates={candidates}
          selectedCandidate={selectedCandidate}
          selectedCurvePoint={selectedCurvePoint}
          onSelectCandidate={onSelectCandidate}
          realCurve={realCurve}
        />
        <GapPeakChart candidates={candidates} selectedCandidate={selectedCandidate} onSelectCandidate={onSelectCandidate} />
      </div>

      <div className="mt-4 rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-medium text-slate-200">Recorrido dinámico</div>
            <div className="text-xs text-slate-500">0 → 1024 · sincroniza curva, gráfica, tabla y vista 3D</div>
          </div>
          <div className="rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1 text-sm text-sky-300">
            curve_idx seleccionado: {selectedCandidate.curve_idx}
          </div>
        </div>
        <input
          type="range"
          min={0}
          max={1024}
          value={sliderValue}
          onChange={(event) => onSliderChange(Number(event.target.value))}
          className="mt-4 h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-800 accent-sky-500"
        />
      </div>
    </SectionCard>
  );
}

function DynamicCurveViewer({
  candidates,
  selectedCandidate,
  selectedCurvePoint,
  onSelectCandidate,
  realCurve,
}: {
  candidates: RegionCandidate[];
  selectedCandidate: RegionCandidate;
  selectedCurvePoint: { x: number; y: number };
  onSelectCandidate: (candidate: RegionCandidate) => void;
  realCurve?: SpineCurveRow[];
}) {
  const bounds = useMemo(() => curveBoundsFromCandidates(candidates), [candidates]);
  const path = useMemo(
    () => realCurve ? buildRealCurvePath(realCurve) : buildCurvePath(bounds),
    [bounds, realCurve],
  );

  return (
    <div className="rounded-2xl border border-[#1e324a] bg-[#091320] p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-sm font-medium text-slate-100">Curva anatómica reconstruida</div>
          <div className="text-xs text-slate-500">Curva azul · centroides verdes · peaks/gaps rojos o naranjas</div>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-sky-400" /> Curva</span>
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> Centroides</span>
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-orange-400" /> Peaks</span>
        </div>
      </div>
      <svg viewBox="0 0 320 600" className="h-[clamp(260px,38vh,380px)] w-full rounded-2xl border border-[#1e324a] bg-[radial-gradient(circle_at_top,#12314f,#09111c_58%)]">
        <rect x="75" y="28" width="170" height="544" rx="26" fill="rgba(15, 23, 42, 0.42)" />
        <path d={path} fill="none" stroke="#2196f3" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
        {candidates.map((candidate) => {
          const point = realCurve
            ? curvePointFromRealData(candidate.curve_idx, realCurve)
            : curvePointForCandidate(candidate, bounds);
          const selected = candidate.peak_idx === selectedCandidate.peak_idx;
          return (
            <g key={candidate.peak_idx} onClick={() => onSelectCandidate(candidate)} className="cursor-pointer">
              <circle cx={point.x} cy={point.y} r={selected ? 8 : 5} fill="#22c55e" stroke="#bef264" strokeWidth="1.5" />
              <polygon
                points={`${point.x - 8},${point.y - 15} ${point.x + 8},${point.y - 15} ${point.x},${point.y - 28}`}
                fill={candidate.kind === 'gap_peak' ? '#ef4444' : '#f97316'}
                opacity={selected ? 1 : 0.82}
              />
            </g>
          );
        })}
        <circle cx={selectedCurvePoint.x} cy={selectedCurvePoint.y} r={11} fill="none" stroke="#f8fafc" strokeWidth="2" />
      </svg>
    </div>
  );
}

function GapPeakChart({
  candidates,
  selectedCandidate,
  onSelectCandidate,
}: {
  candidates: RegionCandidate[];
  selectedCandidate: RegionCandidate;
  onSelectCandidate: (candidate: RegionCandidate) => void;
}) {
  return (
    <div className="rounded-2xl border border-[#1e324a] bg-[#091320] p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-sm font-medium text-slate-100">Señales normalizadas</div>
          <div className="text-xs text-slate-500">Intervertebral · Boundary · Señal combinada · Peaks/gaps</div>
        </div>
        <div className="rounded-full border border-[#1e324a] bg-[#102033] px-3 py-1 text-xs text-slate-400">
          punto activo #{selectedCandidate.peak_idx}
        </div>
      </div>
      <div className="h-[clamp(260px,38vh,380px)]">
        <ResponsiveContainer>
          <ComposedChart data={candidates} margin={{ left: 4, right: 10, top: 18, bottom: 4 }}>
            <CartesianGrid stroke="#16314d" strokeDasharray="4 4" />
            <XAxis dataKey="curve_idx" stroke="#7f95ae" tick={{ fill: '#94a3b8', fontSize: 11 }} />
            <YAxis stroke="#7f95ae" tick={{ fill: '#94a3b8', fontSize: 11 }} domain={[0, 1.2]} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ color: '#cbd5e1', fontSize: '12px' }} />
            <Line type="monotone" dataKey="intervertebral_norm" stroke="#22c55e" strokeWidth={2} dot={false} name="Intervertebral" />
            <Line type="monotone" dataKey="boundary_norm" stroke="#2196f3" strokeWidth={2} dot={false} name="Boundary" />
            <Line type="monotone" dataKey="combined_signal" stroke="#facc15" strokeWidth={2.4} dot={false} name="Señal combinada" />
            <Scatter
              data={candidates}
              dataKey="peak_height"
              fill="#ef4444"
              name="Peaks/gaps"
              shape={(props) => {
                const payload = props.payload as RegionCandidate;
                const active = payload.peak_idx === selectedCandidate.peak_idx;
                return (
                  <circle
                    cx={props.cx}
                    cy={props.cy}
                    r={active ? 7 : 4.5}
                    fill={payload.kind === 'gap_peak' ? '#ef4444' : '#f97316'}
                    stroke={active ? '#ffffff' : 'none'}
                    strokeWidth={2}
                    onClick={() => onSelectCandidate(payload)}
                    style={{ cursor: 'pointer' }}
                  />
                );
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function SpineHeatmap3D({
  candidates,
  selectedPeakIdx,
  metricMode,
  rotation,
  zoom,
  onRotateChange,
  onZoomChange,
  onReset,
  onMetricChange,
  onSelectCandidate,
  realCurve,
}: {
  candidates: RegionCandidate[];
  selectedPeakIdx: number;
  metricMode: MetricMode;
  rotation: number;
  zoom: number;
  onRotateChange: (value: number) => void;
  onZoomChange: (value: number) => void;
  onReset: () => void;
  onMetricChange: (value: MetricMode) => void;
  onSelectCandidate: (candidate: RegionCandidate) => void;
  realCurve?: SpineCurveRow[];
}) {
  const bounds = useMemo(() => curveBoundsFromCandidates(candidates), [candidates]);

  return (
    <SectionCard title="Vista 3D - Análisis de calor" icon={<Sparkles className="h-4 w-4 text-sky-400" />}>
      <div className="flex flex-wrap items-center gap-2">
        <ActionChip icon={<ZoomIn className="h-3.5 w-3.5" />} label="Zoom +" onClick={() => onZoomChange(Number((zoom + 0.08).toFixed(2)))} />
        <ActionChip icon={<ZoomOut className="h-3.5 w-3.5" />} label="Zoom -" onClick={() => onZoomChange(Number(Math.max(0.7, zoom - 0.08).toFixed(2)))} />
        <ActionChip icon={<RotateCcw className="h-3.5 w-3.5" />} label="Restablecer" onClick={onReset} />
      </div>

      <div className="mt-4 rounded-2xl border border-[#1e324a] bg-[#091320] p-4">
        <div
          className="relative h-[clamp(300px,42vh,460px)] overflow-hidden rounded-2xl border border-[#16314d] bg-[radial-gradient(circle_at_top,#143150,#08111c_60%)]"
          style={{ perspective: '1100px' }}
        >
          <div className="pointer-events-none absolute inset-x-6 bottom-5 top-10 rounded-2xl border border-slate-500/10 bg-[linear-gradient(180deg,rgba(148,163,184,0.06),rgba(2,6,23,0.25))] [transform:rotateX(68deg)_translateZ(-40px)]" />
          <div
            className="absolute inset-0 transition-transform duration-300"
            style={{ transform: `rotateX(22deg) rotateY(18deg) scale(${zoom})`, transformStyle: 'preserve-3d', transformOrigin: 'center center' }}
          >
            {candidates.map((candidate) => {
              const s = 34;
              const half = 17;
              const point = realCurve
                ? curvePointFromRealData(candidate.curve_idx, realCurve)
                : curvePointForCandidate(candidate, bounds);
              const t = curveTFromIdx(candidate.curve_idx, bounds);
              const metricValue = candidate[metricMode];
              const color = heatColor(metricValue, metricMode);
              const active = candidate.peak_idx === selectedPeakIdx;
              const depth = Math.round((candidate.peak_height + candidate.gap_strength_mean) * 42);
              return (
                <div
                  key={candidate.peak_idx}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectCandidate(candidate)}
                  className="absolute cursor-pointer focus:outline-none"
                  style={{
                    left: `${Math.max(6, Math.min(80, 18 + ((point.x - 80) / 160) * 64))}%`,
                    top: `${Math.max(4, Math.min(84, 8 + t * 78))}%`,
                    width: s,
                    height: s,
                    transformStyle: 'preserve-3d',
                    transform: `translate(-50%, -50%) translateZ(${depth}px)`,
                  }}
                >
                  {/* Front face */}
                  <div
                    className="absolute inset-0"
                    style={{
                      background: color,
                      transform: `translateZ(${half}px)`,
                      border: active ? '2px solid #f8fafc' : '1px solid rgba(255,255,255,0.18)',
                      boxShadow: active
                        ? '0 0 16px rgba(33,150,243,0.85), 0 4px 16px rgba(0,0,0,0.4)'
                        : '0 4px 14px rgba(0,0,0,0.35)',
                    }}
                  />
                  {/* Top face */}
                  <div
                    className="absolute inset-0"
                    style={{
                      background: color,
                      filter: 'brightness(1.55)',
                      transform: `rotateX(-90deg) translateZ(${half}px)`,
                      border: '1px solid rgba(255,255,255,0.12)',
                    }}
                  />
                  {/* Right face */}
                  <div
                    className="absolute inset-0"
                    style={{
                      background: color,
                      filter: 'brightness(0.48)',
                      transform: `rotateY(90deg) translateZ(${half}px)`,
                      border: '1px solid rgba(255,255,255,0.06)',
                    }}
                  />
                  {/* Cluster label */}
                  <span
                    className="pointer-events-none absolute"
                    style={{
                      top: -11,
                      left: '50%',
                      transform: `translateX(-50%) translateZ(${half + 6}px)`,
                      background: '#07111f',
                      border: '1px solid #1e324a',
                      borderRadius: '999px',
                      padding: '1px 5px',
                      fontSize: '9px',
                      color: '#cbd5e1',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {candidate.cluster_id}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto] md:items-start">
          <div className="rounded-xl border border-[#1e324a] bg-[#102033] px-3 py-2 text-sm text-slate-300">
            Métrica activa: {metricMode.replaceAll('_', ' ')}
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500 md:justify-end">
            <span>Menor intensidad</span>
            <div className="h-2 w-20 rounded-full bg-gradient-to-r from-[#1d4ed8] via-[#10b981] via-50% via-[#facc15] to-[#ef4444]" />
            <span>Mayor intensidad</span>
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

function SelectedPointDetailPanel({
  candidate,
  clusterName,
}: {
  candidate: RegionCandidate;
  clusterName: string;
}) {
  const detailRows = [
    ['Peak index', `${candidate.peak_idx}`],
    ['Vertebra ID', `${candidate.vertebra_id}`],
    ['Región anatómica', readableRegion(candidate.anatomic_region_probable)],
    ['Cluster', clusterName],
    ['Curve idx', `${candidate.curve_idx}`],
    ['t_norm', candidate.t_norm.toFixed(3)],
    ['Gap strength media', candidate.gap_strength_mean.toFixed(3)],
    ['Peak height', candidate.peak_height.toFixed(3)],
    ['Prominence', candidate.prominence.toFixed(3)],
    ['Wavelength prev', `${candidate.wavelength_prev} px`],
    ['Wavelength next', `${candidate.wavelength_next} px`],
    ['Probabilidad', candidate.cluster_probability.toFixed(3)],
  ];

  return (
    <SectionCard title="Detalle del punto seleccionado" icon={<Crosshair className="h-4 w-4 text-sky-400" />}>
      <div className="grid gap-3">
        {detailRows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-3">
            <span className="text-sm text-slate-400">{label}</span>
            <span className="text-sm font-medium text-slate-100">{value}</span>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

function RegionCandidateTable({
  candidates,
  selectedPeakIdx,
  onSelectCandidate,
}: {
  candidates: RegionCandidate[];
  selectedPeakIdx: number;
  onSelectCandidate: (candidate: RegionCandidate) => void;
}) {
  return (
    <SectionCard title="Detalle de regiones candidatas" icon={<Layers3 className="h-4 w-4 text-sky-400" />}>
      <div className="overflow-x-auto rounded-2xl border border-[#1e324a]">
        <div className="max-h-[clamp(400px,72vh,1100px)] overflow-y-auto">
          <table className="min-w-full divide-y divide-[#19304a] text-xs">
            <thead className="sticky top-0 z-10 bg-[#0f2033] text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                {[
                  'peak_idx',
                  'curve_idx',
                  't_norm',
                  'vertebra_id',
                  'región anatómica',
                  'cluster_id',
                  'cluster_prob',
                  'cluster_entropy',
                  'gap_strength_mean',
                  'peak_height',
                  'peak_highpass',
                  'left_gap',
                  'right_gap',
                  'wl_prev',
                  'wl_next',
                ].map((header) => (
                  <th key={header} className="whitespace-nowrap px-3 py-2 font-medium">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#13283f] bg-[#091320] text-slate-200">
              {candidates.map((candidate) => {
                const selected = candidate.peak_idx === selectedPeakIdx;
                return (
                  <tr
                    key={candidate.peak_idx}
                    onClick={() => onSelectCandidate(candidate)}
                    className={`cursor-pointer transition-colors ${selected ? 'bg-sky-500/15' : 'hover:bg-[#102033]'}`}
                    style={{ boxShadow: selected ? 'inset 3px 0 0 #2196f3' : undefined }}
                  >
                    <td className="whitespace-nowrap px-3 py-2">{candidate.peak_idx}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.curve_idx}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.t_norm.toFixed(3)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.vertebra_id}</td>
                    <td className="whitespace-nowrap px-3 py-2">{readableRegion(candidate.anatomic_region_probable)}</td>
                    <td className="whitespace-nowrap px-3 py-2">
                      <span
                        className="rounded-full px-2 py-1 text-xs"
                        style={{ backgroundColor: `${clusterColor(candidate.cluster_id)}20`, color: clusterColor(candidate.cluster_id) }}
                      >
                        {candidate.cluster_id}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.cluster_probability.toFixed(4)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.cluster_entropy.toFixed(4)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.gap_strength_mean.toFixed(3)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.peak_height.toFixed(3)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.peak_highpass_value.toFixed(3)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.left_gap_strength.toFixed(3)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.right_gap_strength.toFixed(3)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.wavelength_prev}</td>
                    <td className="whitespace-nowrap px-3 py-2">{candidate.wavelength_next}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </SectionCard>
  );
}

function ImageTabLayout({
  title,
  imageSrc,
  metadata,
}: {
  title: string;
  imageSrc?: string;
  metadata: [string, string][];
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1.45fr_0.75fr]">
      <SectionCard title={title} icon={<ScanLine className="h-4 w-4 text-sky-400" />}>
        <div className="overflow-hidden rounded-2xl border border-[#1e324a] bg-[#091320] p-3">
          {imageSrc ? (
            <img
              src={imageSrc}
              alt={title}
              className="h-[clamp(220px,44vh,460px)] w-full rounded-2xl object-contain bg-[#07111f]"
            />
          ) : (
            <div className="flex h-[clamp(220px,44vh,460px)] w-full items-center justify-center rounded-2xl border border-dashed border-[#1e324a] bg-[#07111f] text-sm text-slate-400">
              La respuesta llegó, pero no trae una URL utilizable para esta imagen.
            </div>
          )}
        </div>
      </SectionCard>
      <SectionCard title="Metadatos" icon={<ClipboardList className="h-4 w-4 text-sky-400" />}>
        <div className="grid gap-3">
          {metadata.map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</div>
              <div className="mt-2 text-sm text-slate-100">{value}</div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}

function ProcessedImageTab({
  imageSrc,
  summary,
  selectedCandidate,
}: {
  imageSrc: string;
  summary: PatientSummary['summary'];
  selectedCandidate: RegionCandidate;
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1.45fr_0.8fr]">
      <SectionCard title="Imagen procesada" icon={<Waves className="h-4 w-4 text-sky-400" />}>
        <div className="overflow-hidden rounded-2xl border border-[#1e324a] bg-[#091320] p-4">
          <img src={imageSrc} alt="Panel procesado" className="h-[clamp(250px,52vh,520px)] w-full rounded-2xl object-cover" />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <LegendPill color={colors.active} label="Línea azul: curva anatómica" />
          <LegendPill color={colors.green} label="Verde: centroides" />
          <LegendPill color={colors.orange} label="Rojo/Naranja: peaks/gaps" />
        </div>
      </SectionCard>
      <SectionCard title="Métricas rápidas" icon={<Gauge className="h-4 w-4 text-sky-400" />}>
        <MetricRow label="Cobb probabilístico" value={`${summary.cobb_angle.toFixed(2)}°`} accent={colors.active} />
        <MetricRow label="Gaps" value={`${summary.n_gaps}`} accent={colors.yellow} />
        <MetricRow label="Clusters" value={`${summary.n_clusters}`} accent={colors.purple} />
        <MetricRow label="Severidad" value={severityLabel(summary.severity)} accent={colors.green} />
        <div className="mt-4 rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-4 text-sm text-slate-300">
          <div className="mb-2 text-slate-100">Punto activo</div>
          <div>peak #{selectedCandidate.peak_idx} · vertebra {selectedCandidate.vertebra_id}</div>
          <div className="mt-1 text-slate-500">{readableRegion(selectedCandidate.anatomic_region_probable)}</div>
        </div>
      </SectionCard>
    </div>
  );
}

function StructuralAnalysisStandalone({ imageSrc }: { imageSrc: string }) {
  return (
    <SectionCard title="Análisis estructural" icon={<ScanLine className="h-4 w-4 text-sky-400" />}>
      <div className="overflow-hidden rounded-2xl border border-[#1e324a] bg-[#091320] p-4">
        <img src={imageSrc} alt="Analysis grid" className="h-[clamp(280px,58vh,560px)] w-full rounded-2xl object-cover" />
      </div>
      <div className="mt-4 rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-4 text-sm text-slate-300">
        Esta vista compara la señal intervertebral, los bordes anatómicos y la señal combinada usada para detectar
        gaps y regiones vertebrales.
      </div>
    </SectionCard>
  );
}

function DynamicCurveTab({
  curveProxy,
  candidates,
  clusters,
  selectedCandidate,
  selectedCurvePoint,
  sliderValue,
  clusterFilter,
  regionFilter,
  onClusterFilterChange,
  onRegionFilterChange,
  onSliderChange,
  onSelectCandidate,
}: {
  curveProxy: CurveProxy;
  candidates: RegionCandidate[];
  clusters: ClusterSummary[];
  selectedCandidate: RegionCandidate;
  selectedCurvePoint: { x: number; y: number };
  sliderValue: number;
  clusterFilter: 'all' | number;
  regionFilter: 'all' | RegionName;
  onClusterFilterChange: (value: 'all' | number) => void;
  onRegionFilterChange: (value: 'all' | RegionName) => void;
  onSliderChange: (value: number) => void;
  onSelectCandidate: (candidate: RegionCandidate) => void;
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1.05fr_1.1fr_0.8fr]">
      <DynamicCurveViewer
        curveProxy={curveProxy}
        candidates={candidates}
        selectedCandidate={selectedCandidate}
        selectedCurvePoint={selectedCurvePoint}
        onSelectCandidate={onSelectCandidate}
      />
      <div className="grid gap-5">
        <SectionCard title="Gráfica gap / peak interactiva" icon={<BrainCircuit className="h-4 w-4 text-sky-400" />}>
          <div className="mb-4 grid gap-3 md:grid-cols-2">
            <select
              value={clusterFilter}
              onChange={(event) =>
                onClusterFilterChange(event.target.value === 'all' ? 'all' : Number(event.target.value))
              }
              className="rounded-xl border border-[#1e324a] bg-[#102033] px-3 py-2 text-sm text-slate-100 outline-none"
            >
              <option value="all">Filtro por cluster</option>
              {clusters.map((entry) => (
                <option key={entry.clusterId} value={entry.clusterId}>
                  {entry.name}
                </option>
              ))}
            </select>
            <select
              value={regionFilter}
              onChange={(event) => onRegionFilterChange(event.target.value as 'all' | RegionName)}
              className="rounded-xl border border-[#1e324a] bg-[#102033] px-3 py-2 text-sm text-slate-100 outline-none"
            >
              <option value="all">Filtro por región</option>
              <option value="upper_thoracic_probable">upper_thoracic_probable</option>
              <option value="thoracic_probable">thoracic_probable</option>
              <option value="thoracolumbar_probable">thoracolumbar_probable</option>
              <option value="lumbar_probable">lumbar_probable</option>
            </select>
          </div>
          <GapPeakChart candidates={candidates} selectedCandidate={selectedCandidate} onSelectCandidate={onSelectCandidate} />
          <div className="mt-4 rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-4">
            <div className="mb-2 text-sm font-medium text-slate-100">Recorrido anatómico</div>
            <input
              type="range"
              min={0}
              max={1024}
              value={sliderValue}
              onChange={(event) => onSliderChange(Number(event.target.value))}
              className="h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-800 accent-sky-500"
            />
          </div>
        </SectionCard>
        <RegionCandidateTable
          candidates={candidates}
          selectedPeakIdx={selectedCandidate.peak_idx}
          onSelectCandidate={onSelectCandidate}
        />
      </div>
      <SelectedPointDetailPanel candidate={selectedCandidate} clusterName={`Cluster ${selectedCandidate.cluster_id}`} />
    </div>
  );
}

function HeatmapTab({
  candidates,
  clusters,
  selectedCandidate,
  curveProxy,
  metricMode,
  rotation,
  zoom,
  clusterFilter,
  summary,
  onClusterFilterChange,
  onMetricChange,
  onRotateChange,
  onZoomChange,
  onReset,
  onSelectCandidate,
}: {
  candidates: RegionCandidate[];
  clusters: ClusterSummary[];
  selectedCandidate: RegionCandidate;
  curveProxy: CurveProxy;
  metricMode: MetricMode;
  rotation: number;
  zoom: number;
  clusterFilter: 'all' | number;
  summary: PatientSummary['summary'];
  onClusterFilterChange: (value: 'all' | number) => void;
  onMetricChange: (value: MetricMode) => void;
  onRotateChange: (value: number) => void;
  onZoomChange: (value: number) => void;
  onReset: () => void;
  onSelectCandidate: (candidate: RegionCandidate) => void;
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1.45fr_0.85fr]">
      <SpineHeatmap3D
        candidates={candidates}
        selectedPeakIdx={selectedCandidate.peak_idx}
        curveProxy={curveProxy}
        metricMode={metricMode}
        rotation={rotation}
        zoom={zoom}
        onRotateChange={onRotateChange}
        onZoomChange={onZoomChange}
        onReset={onReset}
        onMetricChange={onMetricChange}
        onSelectCandidate={onSelectCandidate}
      />
      <SectionCard title="Controles laterales" icon={<Gauge className="h-4 w-4 text-sky-400" />}>
        <div className="grid gap-4">
          <div>
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">Selector de cluster</div>
            <select
              value={clusterFilter}
              onChange={(event) =>
                onClusterFilterChange(event.target.value === 'all' ? 'all' : Number(event.target.value))
              }
              className="w-full rounded-xl border border-[#1e324a] bg-[#102033] px-3 py-2 text-sm text-slate-100 outline-none"
            >
              <option value="all">Todos los clusters</option>
              {clusters.map((entry) => (
                <option key={entry.clusterId} value={entry.clusterId}>
                  {entry.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">Métrica activa</div>
            <div className="rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-4 text-sm text-slate-200">
              {metricMode.replaceAll('_', ' ')}
            </div>
          </div>
          <div className="rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-4 text-sm">
            <div className="text-slate-400">Bloque activo</div>
            <div className="mt-2 text-lg font-semibold text-slate-100">Vért. {selectedCandidate.vertebra_id}</div>
            <div className="mt-1 text-slate-400">{readableRegion(selectedCandidate.anatomic_region_probable)}</div>
            <div className="mt-3 grid gap-2 text-slate-200">
              <div className="flex items-center justify-between"><span>gap_strength_mean</span><span>{selectedCandidate.gap_strength_mean.toFixed(3)}</span></div>
              <div className="flex items-center justify-between"><span>peak_height</span><span>{selectedCandidate.peak_height.toFixed(3)}</span></div>
              <div className="flex items-center justify-between"><span>cluster_probability</span><span>{selectedCandidate.cluster_probability.toFixed(3)}</span></div>
              <div className="flex items-center justify-between"><span>entropy</span><span>{selectedCandidate.cluster_entropy.toFixed(3)}</span></div>
            </div>
          </div>
          <div className="rounded-2xl border border-orange-500/30 bg-orange-500/10 px-4 py-3 text-sm text-orange-200">
            {summary.warning}
          </div>
        </div>
      </SectionCard>
    </div>
  );
}

function PatchColumn({
  patches,
  selectedPeakIdx,
  onSelectPatch,
}: {
  patches: PatchInfo[];
  selectedPeakIdx: number;
  onSelectPatch: (peakIdx: number) => void;
}) {
  return (
    <SectionCard title={`Parches · posición (${patches.length})`} icon={<Layers3 className="h-4 w-4 text-sky-400" />}>
      <div className="max-h-[clamp(320px,62vh,860px)] space-y-2 overflow-y-auto pr-1">
        {patches.map((patch) => {
          const active = patch.peakIdx === selectedPeakIdx;
          return (
            <button
              key={patch.id}
              type="button"
              onClick={() => onSelectPatch(patch.peakIdx)}
              className={`w-full overflow-hidden rounded-xl border text-left transition-all ${
                active
                  ? 'border-sky-500 bg-sky-500/10 ring-1 ring-sky-500/40'
                  : 'border-[#1e324a] bg-[#091320] hover:border-sky-800'
              }`}
            >
              <div className="flex items-center gap-3 p-2">
                <img src={patch.src} alt={`Parche ${patch.id}`} className="h-14 w-14 flex-shrink-0 rounded-lg object-cover" />
                <div className="min-w-0 flex-1 text-xs">
                  <div className="truncate font-medium text-slate-100">{patch.region}</div>
                  <div className="mt-0.5 text-slate-400">Cluster {patch.clusterId}</div>
                  <div className="mt-0.5 text-slate-500">gap {patch.intensity.toFixed(2)}</div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </SectionCard>
  );
}

function PatchGrid({ patches, onSelectPeak }: { patches: PatchInfo[]; onSelectPeak: (peak: number) => void }) {
  return (
    <SectionCard title={`Parches (${patches.length})`} icon={<Layers3 className="h-4 w-4 text-sky-400" />}>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {patches.map((patch) => (
          <button
            key={patch.id}
            type="button"
            onClick={() => onSelectPeak(patch.id - 1)}
            className="overflow-hidden rounded-2xl border border-[#1e324a] bg-[#091320] text-left transition-transform hover:-translate-y-1"
          >
            <img src={patch.src} alt={`Parche ${patch.id}`} className="h-36 w-full object-cover" />
            <div className="space-y-2 px-4 py-4 text-sm">
              <div className="flex items-center justify-between text-slate-100">
                <span>Parche {patch.id}</span>
                <ChevronRight className="h-4 w-4 text-slate-500" />
              </div>
              <div className="text-slate-400">{patch.region}</div>
              <div className="flex items-center justify-between text-slate-300">
                <span>Cluster {patch.clusterId}</span>
                <span>{patch.intensity.toFixed(2)}</span>
              </div>
            </div>
          </button>
        ))}
      </div>
    </SectionCard>
  );
}

function SectionCard({
  title,
  icon,
  children,
  className = '',
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-[24px] border border-[#1e324a] bg-[#0d1a2b] px-4 py-4 shadow-[0_16px_40px_rgba(0,0,0,0.22)] ${className}`}>
      <div className="mb-3 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-sky-500/20 bg-sky-500/10">{icon}</div>
        <div>
          <h2 className="text-base font-semibold text-slate-100">{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

function MetricRow({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-3">
      <span className="text-sm text-slate-400">{label}</span>
      <span className="text-sm font-semibold" style={{ color: accent }}>
        {value}
      </span>
    </div>
  );
}

function MetricSparkline({
  label,
  value,
  data,
  color,
}: {
  label: string;
  value: string;
  data: number[];
  color: string;
}) {
  return (
    <div className="rounded-2xl border border-[#1e324a] bg-[#102033] px-4 py-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-300">{label}</div>
        <div className="text-sm font-semibold" style={{ color }}>
          {value}
        </div>
      </div>
      <MiniSparkline data={data} color={color} />
    </div>
  );
}

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  const width = 240;
  const height = 54;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const points = data
    .map((value, index) => {
      const x = (index / (data.length - 1)) * width;
      const y = height - ((value - min) / (max - min || 1)) * (height - 10) - 5;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="mt-3 h-14 w-full">
      <polyline fill="none" stroke={color} strokeWidth="3" points={points} />
    </svg>
  );
}

function LegendPill({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-[#1e324a] bg-[#102033] px-3 py-2 text-sm text-slate-300">
      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
      <span>{label}</span>
    </div>
  );
}

function ActionChip({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-full border border-[#1e324a] bg-[#102033] px-3 py-2 text-xs text-slate-300 transition-colors hover:border-sky-500/40 hover:text-slate-100"
    >
      {icon}
      {label}
    </button>
  );
}

function readableRegion(region: RegionName) {
  return region.replaceAll('_probable', '').replaceAll('_', ' ');
}

function clusterColor(clusterId: number) {
  const match = clusterSummary.find((entry) => entry.clusterId === clusterId);
  return match?.color ?? colors.active;
}

function curveBoundsFromCandidates(candidates: RegionCandidate[]): CurveBounds {
  if (!candidates.length) {
    return { minCurveIdx: 0, maxCurveIdx: 1024 };
  }

  let minCurveIdx = Number.POSITIVE_INFINITY;
  let maxCurveIdx = Number.NEGATIVE_INFINITY;
  candidates.forEach((candidate) => {
    minCurveIdx = Math.min(minCurveIdx, candidate.curve_idx);
    maxCurveIdx = Math.max(maxCurveIdx, candidate.curve_idx);
  });

  if (!Number.isFinite(minCurveIdx) || !Number.isFinite(maxCurveIdx) || minCurveIdx === maxCurveIdx) {
    return { minCurveIdx: 0, maxCurveIdx: 1024 };
  }

  return { minCurveIdx, maxCurveIdx };
}

function curveTFromIdx(curveIdx: number, bounds: CurveBounds) {
  const range = Math.max(bounds.maxCurveIdx - bounds.minCurveIdx, 1);
  return Math.max(0, Math.min(1, (curveIdx - bounds.minCurveIdx) / range));
}

function curvePointFromIdx(curveIdx: number, bounds: CurveBounds): CurvePoint {
  const t = curveTFromIdx(curveIdx, bounds);
  return {
    x: 160 + Math.sin(t * Math.PI * 1.25) * 42 + (t - 0.5) * 34,
    y: 34 + t * 520,
  };
}

function buildCurvePath(bounds: CurveBounds, samples = 96) {
  const total = Math.max(samples, 2);
  const range = Math.max(bounds.maxCurveIdx - bounds.minCurveIdx, 1);
  return Array.from({ length: total }, (_, index) => {
    const curveIdx = bounds.minCurveIdx + (index / (total - 1)) * range;
    const point = curvePointFromIdx(curveIdx, bounds);
    return `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`;
  }).join(' ');
}

function curvePointForCandidate(candidate: RegionCandidate, bounds: CurveBounds) {
  return curvePointFromIdx(candidate.curve_idx, bounds);
}

function heatColor(value: number, mode: MetricMode) {
  const normalized = mode === 'cluster_entropy' ? 1 - Math.min(value / 0.1, 1) : Math.min(value, 1);
  if (normalized < 0.2) return '#1d4ed8';
  if (normalized < 0.4) return '#06b6d4';
  if (normalized < 0.6) return '#22c55e';
  if (normalized < 0.8) return '#facc15';
  if (normalized < 0.92) return '#f97316';
  return '#ef4444';
}

// ─── CSV parsing utilities ────────────────────────────────────────────────────

function parseCSV(text: string): Record<string, string>[] {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const values = line.split(',');
    return Object.fromEntries(headers.map((h, i) => [h, (values[i] ?? '').trim()]));
  });
}

function parseRegionsCSV(text: string): RegionCandidate[] {
  return parseCSV(text)
    .filter((row) => row.peak_idx !== undefined && row.peak_idx !== '')
    .map((row, index) => ({
      peak_idx: parseInt(row.peak_idx || '') || index + 1,
      curve_idx: parseFloat(row.curve_idx || '') || 0,
      t_norm: parseFloat(row.t_norm || '') || 0,
      vertebra_id: parseInt(row.vertebra_id || '') || index + 1,
      anatomic_region_probable: (row.anatomic_region_probable as RegionName) || 'thoracic_probable',
      cluster_id: parseInt(row.cluster_id || '') || 0,
      cluster_probability: parseFloat(row.cluster_probability || '') || 0,
      cluster_entropy: parseFloat(row.cluster_entropy || '') || 0,
      gap_strength_mean: parseFloat(row.gap_strength_mean || '') || 0,
      peak_height: parseFloat(row.peak_height || '') || 0,
      peak_highpass_value: parseFloat(row.peak_highpass_value || '') || 0,
      left_gap_strength: parseFloat(row.left_gap_strength || '') || 0,
      right_gap_strength: parseFloat(row.right_gap_strength || '') || 0,
      wavelength_prev: parseFloat(row.wavelength_prev || '') || 0,
      wavelength_next: parseFloat(row.wavelength_next || '') || 0,
      kind: 'gap_peak' as const,
      intervertebral_norm: 0,
      boundary_norm: 0,
      combined_signal: 0,
      prominence: 0,
    }));
}

function parseCurveCSV(text: string): SpineCurveRow[] {
  return parseCSV(text)
    .filter((row) => row.curve_idx !== undefined && row.curve_idx !== '')
    .map((row) => ({
      curve_idx: parseFloat(row.curve_idx || '') || 0,
      x_curve: parseFloat(row.x_curve || '') || 0,
      y_curve: parseFloat(row.y_curve || '') || 0,
      t_norm: parseFloat(row.t_norm || '') || 0,
    }));
}

function parsePeaksCSV(text: string): PeakCurveRow[] {
  return parseCSV(text)
    .filter((row) => row.centroid_curve_x !== undefined && row.centroid_curve_x !== '')
    .map((row) => ({
      centroid_curve_x: parseFloat(row.centroid_curve_x || '') || 0,
      centroid_curve_y: parseFloat(row.centroid_curve_y || '') || 0,
      centroid_t_norm: parseFloat(row.centroid_t_norm || '') || 0,
      spatial_order: parseFloat(row.spatial_order || '') || 0,
    }));
}

function curvePointFromRealData(curveIdx: number, realCurve: SpineCurveRow[]): CurvePoint {
  if (!realCurve.length) return { x: 160, y: 300 };
  let best = realCurve[0];
  for (const row of realCurve) {
    if (Math.abs(row.curve_idx - curveIdx) < Math.abs(best.curve_idx - curveIdx)) best = row;
  }
  const xValues = realCurve.map((r) => r.x_curve);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const xRange = Math.max(xMax - xMin, 1);
  const xNorm = (best.x_curve - xMin) / xRange;
  return {
    x: 80 + xNorm * 160,
    y: 34 + best.t_norm * 520,
  };
}

function buildRealCurvePath(realCurve: SpineCurveRow[]): string {
  if (!realCurve.length) return '';
  const xValues = realCurve.map((r) => r.x_curve);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const xRange = Math.max(xMax - xMin, 1);
  const step = Math.max(1, Math.floor(realCurve.length / 96));
  const pts = realCurve
    .filter((_, i) => i % step === 0)
    .map((row) => ({
      x: 80 + ((row.x_curve - xMin) / xRange) * 160,
      y: 34 + row.t_norm * 520,
    }));
  if (pts.length < 2) return `M ${pts[0].x} ${pts[0].y}`;
  const d: string[] = [`M ${pts[0].x} ${pts[0].y}`];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d.push(`C ${cp1x} ${cp1y} ${cp2x} ${cp2y} ${p2.x} ${p2.y}`);
  }
  return d.join(' ');
}

function buildPanelImage(title: string, subtitle: string, accent: string, includeSignal = false) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 600">
      <defs>
        <linearGradient id="bg" x1="0%" x2="100%" y1="0%" y2="100%">
          <stop offset="0%" stop-color="#07111f" />
          <stop offset="100%" stop-color="#10233a" />
        </linearGradient>
      </defs>
      <rect width="900" height="600" fill="url(#bg)" rx="28" />
      <path d="M430 55 C390 150 385 285 438 530" stroke="#93c5fd" stroke-width="18" stroke-linecap="round" fill="none" opacity="0.85" />
      <path d="M465 55 C498 160 503 275 458 530" stroke="#1e3a8a" stroke-width="18" stroke-linecap="round" fill="none" opacity="0.8" />
      ${includeSignal ? '<polyline points="180,420 240,350 300,290 360,310 420,245 480,220 540,150 600,110 660,80" fill="none" stroke="#22c55e" stroke-width="6" />' : ''}
      <rect x="38" y="38" width="824" height="72" rx="18" fill="#0d1a2b" stroke="#1e324a" />
      <text x="70" y="78" fill="#f8fafc" font-size="28" font-family="Arial, sans-serif">${title}</text>
      <text x="70" y="102" fill="#94a3b8" font-size="15" font-family="Arial, sans-serif">${subtitle}</text>
      <rect x="52" y="500" width="260" height="44" rx="14" fill="#0d1a2b" stroke="#1e324a" />
      <text x="78" y="528" fill="${accent}" font-size="18" font-family="Arial, sans-serif">Análisis médico / investigación</text>
    </svg>`;

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function buildAnalysisGridImage() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1300 720">
      <rect width="1300" height="720" fill="#07111f" rx="28" />
      <g font-family="Arial, sans-serif">
        <text x="86" y="78" fill="#f8fafc" font-size="30">Análisis estructural</text>
        <text x="86" y="112" fill="#94a3b8" font-size="16">Imagen · Intervertebral · Boundary · Señal combinada</text>
      </g>
      ${[
        ['Imagen', '#2196f3', 70],
        ['Intervertebral cov=52.0%', '#22c55e', 375],
        ['Boundary cov=46.1%', '#facc15', 680],
        ['Señal combinada', '#ef4444', 985],
      ]
        .map(
          ([label, accent, x]) => `
          <g>
            <rect x="${x}" y="150" width="245" height="500" rx="28" fill="#0d1a2b" stroke="#1e324a" />
            <text x="${Number(x) + 26}" y="192" fill="#f8fafc" font-size="20" font-family="Arial, sans-serif">${label}</text>
            <rect x="${Number(x) + 22}" y="220" width="200" height="390" rx="22" fill="#0f1b2e" stroke="#1e324a" />
            <path d="M${Number(x) + 118} 248 C${Number(x) + 93} 320 ${Number(x) + 90} 450 ${Number(x) + 125} 575" stroke="#e2e8f0" stroke-width="12" fill="none" opacity="0.75" />
            <path d="M${Number(x) + 145} 248 C${Number(x) + 175} 332 ${Number(x) + 180} 444 ${Number(x) + 142} 575" stroke="${accent}" stroke-width="10" fill="none" opacity="0.88" />
            <circle cx="${Number(x) + 128}" cy="420" r="12" fill="${accent}" opacity="0.9" />
          </g>`
        )
        .join('')}
    </svg>`;

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function buildPatchImage(id: number) {
  const intensity = 30 + id * 12;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 180">
      <rect width="240" height="180" fill="#08111d" />
      <rect x="18" y="18" width="204" height="144" rx="18" fill="#10233a" stroke="#1e324a" />
      <path d="M120 36 C102 68 99 104 118 144" stroke="#dbeafe" stroke-width="10" fill="none" />
      <path d="M140 36 C156 74 160 108 142 144" stroke="rgba(34,197,94,0.85)" stroke-width="10" fill="none" />
      <circle cx="140" cy="${50 + id * 6}" r="10" fill="rgba(249,115,22,0.85)" />
      <text x="28" y="156" fill="#f8fafc" font-size="18" font-family="Arial, sans-serif">Patch ${id}</text>
      <text x="154" y="156" fill="#94a3b8" font-size="14" font-family="Arial, sans-serif">I=${intensity}</text>
    </svg>`;

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

const tooltipStyle = {
  backgroundColor: '#0d1a2b',
  border: '1px solid #1e324a',
  borderRadius: '14px',
  color: '#f8fafc',
};