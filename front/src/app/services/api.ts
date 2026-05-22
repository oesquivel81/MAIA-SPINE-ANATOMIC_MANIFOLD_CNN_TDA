import type { AnalysisData, PatientInfo } from '../../../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const ANALYSIS_ENDPOINT =
  import.meta.env.VITE_PIPELINE_RUN_URL || `${API_BASE_URL}/pipeline/run`;
const API_ORIGIN = (() => {
  const baseOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5173';
  return new URL(API_BASE_URL, baseOrigin).origin;
})();

function resolveArtifactUrl(value?: string): string | undefined {
  if (!value) {
    return undefined;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }

  if (trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('data:')) {
    return trimmed;
  }

  if (trimmed.startsWith('/artifacts/')) {
    return `${API_ORIGIN}${trimmed}`;
  }

  const normalized = trimmed.replaceAll('\\', '/');
  const artifactsMarker = '/pipeline_ml_artifacts/';
  if (normalized.includes(artifactsMarker)) {
    const relativePath = normalized.split(artifactsMarker, 2)[1];
    return `${API_ORIGIN}/artifacts/${relativePath}`;
  }

  if (normalized.startsWith('./pipeline_ml_artifacts/')) {
    return `${API_ORIGIN}/artifacts/${normalized.slice('./pipeline_ml_artifacts/'.length)}`;
  }

  if (normalized.startsWith('pipeline_ml_artifacts/')) {
    return `${API_ORIGIN}/artifacts/${normalized.slice('pipeline_ml_artifacts/'.length)}`;
  }

  return trimmed;
}

function extractPatchInputs(
  raw: Record<string, unknown>,
  clinical: Record<string, unknown>,
  images: Record<string, unknown>,
): string[] | undefined {
  const outputs = (raw.outputs as Record<string, unknown> | undefined) || {};

  const directCandidates: unknown[] = [
    images.patch_inputs,
    images.patch_input_paths,
    clinical.patch_inputs,
    clinical.patch_input_paths,
    raw.patch_inputs,
    raw.patch_input_paths,
    outputs.patch_inputs,
    outputs.patch_input_paths,
  ];

  for (const candidate of directCandidates) {
    if (!Array.isArray(candidate)) {
      continue;
    }

    const urls = candidate
      .map((entry) => resolveArtifactUrl(typeof entry === 'string' ? entry : undefined))
      .filter((entry): entry is string => Boolean(entry));

    if (urls.length > 0) {
      return urls;
    }
  }

  const studentOutputs = outputs.student_outputs;
  if (Array.isArray(studentOutputs)) {
    const urls = studentOutputs
      .map((entry) => {
        if (!entry || typeof entry !== 'object') {
          return undefined;
        }
        const record = entry as Record<string, unknown>;
        const value = record.input_path ?? record.patch_input ?? record.patch_input_path;
        return resolveArtifactUrl(typeof value === 'string' ? value : undefined);
      })
      .filter((entry): entry is string => Boolean(entry));

    if (urls.length > 0) {
      return urls;
    }
  }

  return undefined;
}

function normalizeAnalysisResponse(payload: unknown): AnalysisData {
  const raw = payload as Record<string, unknown>;
  const nested = (raw.outputs as Record<string, unknown> | undefined)?.clinical_result as Record<string, unknown> | undefined;
  const clinical = (raw.clinical_result as Record<string, unknown> | undefined) || nested || raw;

  const images = (clinical.images as Record<string, unknown> | undefined) || {};
  const predictions = (clinical.predictions as Record<string, unknown> | undefined) || {};
  const gapSummary = (clinical.gap_summary as Record<string, unknown> | undefined) || {};

  const patchInputs = extractPatchInputs(raw, clinical, images);

  return {
    request_id: String(clinical.request_id ?? raw.request_id ?? ''),
    patient_name: String(clinical.patient_name ?? raw.patient_name ?? ''),
    images: {
      combined_signal: resolveArtifactUrl(images.combined_signal as string | undefined),
      analysis_grid: resolveArtifactUrl(images.analysis_grid as string | undefined),
      gap_peak_analysis: resolveArtifactUrl(images.gap_peak_analysis as string | undefined),
      spatial_index_panel: resolveArtifactUrl(images.spatial_index_panel as string | undefined),
      binary_mask: resolveArtifactUrl(images.binary_mask as string | undefined),
      curve_mask: resolveArtifactUrl(images.curve_mask as string | undefined),
      normalized_image: resolveArtifactUrl(images.normalized_image as string | undefined),
        patch_inputs: patchInputs,
    },
    predictions: {
      inference_done: Boolean(predictions.inference_done),
      cobb_angle_deg: typeof predictions.cobb_angle_deg === 'number' ? predictions.cobb_angle_deg : undefined,
      cobb_severity: typeof predictions.cobb_severity === 'string' ? predictions.cobb_severity : undefined,
      dominant_cluster_id: typeof predictions.dominant_cluster_id === 'number' ? predictions.dominant_cluster_id : undefined,
      n_clusters_detected: typeof predictions.n_clusters_detected === 'number' ? predictions.n_clusters_detected : undefined,
      clinical_json_path: resolveArtifactUrl(predictions.clinical_json_path as string | undefined),
      clinical_figure_path: resolveArtifactUrl(predictions.clinical_figure_path as string | undefined),
      summary_csv_path: resolveArtifactUrl(predictions.summary_csv_path as string | undefined),
      regions_csv_path: resolveArtifactUrl(predictions.regions_csv_path as string | undefined),
    },
    gap_summary: {
      mean_gap_spacing: typeof gapSummary.mean_gap_spacing === 'number' ? gapSummary.mean_gap_spacing : undefined,
      std_gap_spacing: typeof gapSummary.std_gap_spacing === 'number' ? gapSummary.std_gap_spacing : undefined,
      n_peaks: typeof gapSummary.n_peaks === 'number' ? gapSummary.n_peaks : undefined,
      n_gap_peaks: typeof gapSummary.n_gap_peaks === 'number' ? gapSummary.n_gap_peaks : undefined,
      vertebra_csv_path: resolveArtifactUrl(gapSummary.vertebra_csv_path as string | undefined),
    },
    originalImageUrl: undefined,
  };
}

export interface FileMetadata {
  file_id: string;
  filename: string;
  content_type: string;
  size: number;
  upload_date: string;
}

export interface NormalizationResult {
  success: boolean;
  original_image_url?: string;
  normalized_image_url?: string;
  profile_used?: string;
  comparison_data?: {
    original_stats: Record<string, number>;
    normalized_stats: Record<string, number>;
  };
  error?: string;
}

export interface ProfileStatus {
  source_count: number;
  redis_count: number;
  mongo_count: number;
  sample_profiles: Array<{
    profile_id: string;
    stats: Record<string, number>;
  }>;
}

class ApiService {
  async analyzeSpine(file: File, patient: PatientInfo): Promise<AnalysisData> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('nombre', patient.nombre);
    formData.append('apellido_paterno', patient.apellido_paterno);
    formData.append('edad', String(patient.edad));
    formData.append('peso', String(patient.peso));
    formData.append('sexo', patient.sexo);
    formData.append('fecha', patient.fecha);

    console.info('[api-debug] analyzeSpine endpoint', ANALYSIS_ENDPOINT);

    const response = await fetch(ANALYSIS_ENDPOINT, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Spine analysis failed: ${response.statusText}`);
    }

    const payload = await response.json();
    return normalizeAnalysisResponse(payload);
  }

  async uploadFile(file: File): Promise<FileMetadata> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/files`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }

    return response.json();
  }

  async getFileMetadata(fileId: string): Promise<FileMetadata> {
    const response = await fetch(`${API_BASE_URL}/files/${fileId}`);

    if (!response.ok) {
      throw new Error(`Failed to fetch file metadata: ${response.statusText}`);
    }

    return response.json();
  }

  async normalizeImage(
    file: File,
    profileSource?: string,
    compareFile?: File,
    compareProfileJson?: File
  ): Promise<NormalizationResult> {
    const formData = new FormData();
    formData.append('file', file);

    if (profileSource) {
      formData.append('profile_source', profileSource);
    }

    if (compareFile) {
      formData.append('compare_file', compareFile);
    }

    if (compareProfileJson) {
      formData.append('compare_profile_json', compareProfileJson);
    }

    const response = await fetch(`${API_BASE_URL}/normalization/image`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Normalization failed: ${response.statusText}`);
    }

    return response.json();
  }

  async getProfileStatus(sampleSize: number = 5): Promise<ProfileStatus> {
    const response = await fetch(
      `${API_BASE_URL}/normalization/profiles/status?sample_size=${sampleSize}`
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch profile status: ${response.statusText}`);
    }

    return response.json();
  }

  async bootstrapProfiles(): Promise<{
    loaded_to_redis: number;
    loaded_to_mongo: number;
    status: ProfileStatus;
  }> {
    const response = await fetch(`${API_BASE_URL}/normalization/profiles/bootstrap`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`Bootstrap failed: ${response.statusText}`);
    }

    return response.json();
  }

  async checkHealth(): Promise<{ status: string }> {
    const response = await fetch(`${API_BASE_URL}/health`);

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }

    return response.json();
  }
}

export const apiService = new ApiService();
