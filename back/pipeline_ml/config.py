from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class DebugFlags:
    enabled: bool = True
    verbose: bool = True
    print_step_summary: bool = True
    save_debug_artifacts: bool = False
    # Mostrar visualizaciones matplotlib inline (Colab/Jupyter). False en produccion.
    plots_show: bool = False


@dataclass
class RoutingFlags:
    colab_mode: bool = True
    instance_mode: bool = False
    write_local_artifacts: bool = True
    write_outputs_to_s3: bool = False
    write_metrics_to_mongo: bool = False
    publish_events_to_kafka: bool = False
    invoke_lambda_for_metrics: bool = False


@dataclass
class PipelinePaths:
    workspace_root: str = "./"
    local_artifacts_dir: str = "./pipeline_ml_artifacts"
    output_subdir: str = "outputs"
    metrics_subdir: str = "metrics"
    temp_subdir: str = "tmp"

    # Ruta al archivo JSONL de perfiles de normalización.
    # Si está vacío, se busca automáticamente en cwd/resources/NORMALIZATION_PROFILES/
    normalization_profile_jsonl: str = ""

    # Directorio donde se guardan los traces de normalización aplicados (formato N_1_normalization_profile.json)
    # Ruta relativa se resuelve desde cwd (en Colab: /content/resources/NORMALIZATION_PROFILES/patient_json_profiles)
    patient_json_profiles_dir: str = "resources/NORMALIZATION_PROFILES/patient_json_profiles"

    # Ruta al checkpoint del CNN binario/curva (FastBinaryCurveUNet).
    # Ejemplo: /content/experiments/pipeline_model/01_binary_curve_cnn/best_binary_curve_model.pt
    binary_curve_model_path: str = ""

    # URL de Redis para backup del trace (opcional, best-effort)
    # Ejemplo: redis://localhost:6379/0
    redis_url: str = ""

    s3_bucket: str = ""
    s3_prefix: str = "pipeline-ml"

    mongo_database: str = "maia"
    mongo_collection: str = "pipeline_metrics"

    kafka_topic: str = "pipeline-progress"
    lambda_function_name: str = ""


@dataclass
class PipelineConfig:
    debug: DebugFlags = field(default_factory=DebugFlags)
    routing: RoutingFlags = field(default_factory=RoutingFlags)
    paths: PipelinePaths = field(default_factory=PipelinePaths)

    @classmethod
    def from_json_file(cls, config_file: str | None) -> "PipelineConfig":
        if not config_file:
            return cls()

        path = Path(config_file)
        if not path.exists():
            raise FileNotFoundError(f"No existe el archivo de configuracion: {config_file}")

        data = json.loads(path.read_text(encoding="utf-8"))

        debug = DebugFlags(**data.get("debug", {}))
        routing = RoutingFlags(**data.get("routing", {}))
        paths_cfg = PipelinePaths(**data.get("paths", {}))

        return cls(debug=debug, routing=routing, paths=paths_cfg)
