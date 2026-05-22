export interface PatientInfo {
  nombre: string;
  apellido_paterno: string;
  edad: number;
  peso: number;
  sexo: string;
  fecha: string;
}

export interface PipelineImages {
  combined_signal?: string;
  analysis_grid?: string;
  gap_peak_analysis?: string;
  spatial_index_panel?: string;
  binary_mask?: string;
  curve_mask?: string;
  normalized_image?: string;
  patch_inputs?: string[];
}

export interface PipelinePredictions {
  inference_done: boolean;
  cobb_angle_deg?: number;
  cobb_severity?: string;
  dominant_cluster_id?: number;
  n_clusters_detected?: number;
  clinical_json_path?: string;
  clinical_figure_path?: string;
  summary_csv_path?: string;
  regions_csv_path?: string;
}

export interface GapSummary {
  mean_gap_spacing?: number;
  std_gap_spacing?: number;
  n_peaks?: number;
  n_gap_peaks?: number;
  vertebra_csv_path?: string;
}

export interface NerveCurve {
  curve_csv_path?: string;      // 240 puntos de la curva continua
  centroids_csv_path?: string;  // ~N centroides de vértebras proyectados
  peaks_csv_path?: string;      // peaks de gap intervertebral proyectados
  match_csv_path?: string;      // match final centroides ↔ peaks con spatial_order
}

export interface AnalysisData {
  request_id: string;
  patient_name: string;
  images: PipelineImages;
  predictions: PipelinePredictions;
  gap_summary: GapSummary;
  nerve_curve?: NerveCurve;
  originalImageUrl?: string;
}
