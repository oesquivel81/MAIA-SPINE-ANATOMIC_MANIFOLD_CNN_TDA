const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

export interface FileMetadata {
  file_id: string;
  filename: string;
  content_type: string;
  size: number;
  upload_date: string;
}

export interface NormalizationResult {
  success: boolean;
  profile_source: string;
  implementation_map: string[];
  closest_profile_key: string;
  closest_profile_distance: number;
  closest_profile_summary: Record<string, number | string | boolean | null>;
  input_stats: Record<string, number>;
  output_stats: Record<string, number>;
  output_shape: number[];
  output_image_base64: string;
  output_image_url?: string;
  normalized_image_url: string;
  runtime_metadata: Record<string, Record<string, number | string | boolean | (number | string | boolean | null)[] | null>>;
  analysis?: {
    curve?: {
      detected?: boolean;
      direction?: string;
      estimated_cobb_angle?: number;
      severity?: string;
      major_curve_span?: string;
      horizontal_shift?: number;
      max_offset?: number;
      curve_points?: Array<{ x: number; y: number }>;
    };
    color_index?: {
      average_intensity?: number;
      median_intensity?: number;
      bands?: Array<{
        range: string;
        percentage: number;
        color: string;
        count: number;
      }>;
    };
    segmentation?: {
      origin?: string;
      centroid?: { x: number; y: number };
      highlighted_vertebrae?: string[];
      curve_type?: string;
      spine_center_line?: Array<{ x: number; y: number }>;
    };
    heatmap_data?: number[][];
    measurements?: Array<{
      parameter: string;
      value: number | string;
      unit?: string;
      normal_range?: string;
      status?: 'normal' | 'warning' | 'critical' | string;
    }>;
  };
  comparison?: {
    compare_profile_source: string;
    compare_profile_summary: Record<string, number | string | boolean | null>;
    compare_input_stats: Record<string, number>;
    compare_output_stats: Record<string, number>;
    compare_output_shape: number[];
    compare_output_image_base64: string;
    compare_output_image_url?: string;
    comparison_visualization_base64: string;
    comparison_visualization_url?: string;
    compare_profile_payload: Record<string, unknown>;
  } | null;
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
  async uploadFile(file: File): Promise<FileMetadata> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/files`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const message = body?.detail || body?.error || response.statusText;
      throw new Error(`Upload failed: ${message}`);
    }

    return response.json();
  }

  async getFileMetadata(fileId: string): Promise<FileMetadata> {
    const response = await fetch(`${API_BASE_URL}/files/${fileId}`);

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const message = body?.detail || body?.error || response.statusText;
      throw new Error(`Failed to fetch file metadata: ${message}`);
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

    const body = await response.json().catch(() => null);
    if (!response.ok) {
      const message = body?.detail || body?.error || response.statusText;
      throw new Error(`Normalization failed: ${message}`);
    }

    if (!body || !body.output_image_base64) {
      throw new Error('Backend returned an invalid normalization response');
    }

    return {
      ...body,
      normalized_image_url:
        body.output_image_url || `data:image/png;base64,${body.output_image_base64}`,
    } as NormalizationResult;
  }

  async getProfileStatus(sampleSize: number = 5): Promise<ProfileStatus> {
    const response = await fetch(
      `${API_BASE_URL}/normalization/profiles/status?sample_size=${sampleSize}`
    );

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const message = body?.detail || body?.error || response.statusText;
      throw new Error(`Failed to fetch profile status: ${message}`);
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
      const body = await response.json().catch(() => null);
      const message = body?.detail || body?.error || response.statusText;
      throw new Error(`Bootstrap failed: ${message}`);
    }

    return response.json();
  }

  async checkHealth(): Promise<{ status: string }> {
    const response = await fetch(`${API_BASE_URL}/health`);

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const message = body?.detail || body?.error || response.statusText;
      throw new Error(`Health check failed: ${message}`);
    }

    return response.json();
  }
}

export const apiService = new ApiService();
