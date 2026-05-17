const API_BASE_URL = 'http://localhost:8000/api/v1';

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
