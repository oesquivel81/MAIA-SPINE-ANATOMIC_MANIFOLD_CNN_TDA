from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
import json


def _from_dict(cls, data: dict):
    """Construye un dataclass filtrando claves desconocidas del dict.

    Permite que un config.json tenga campos nuevos o antiguos sin romper
    versiones del codigo que aun no los definen.
    """
    valid = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in valid})


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

    # Número de parches cuadrados que CurvePatchStage extrae de la curva espinal.
    # Cada parche cubre un segmento equiponderado de la curva.  Default=8.
    n_curve_patches: int = 8

    # Ruta al checkpoint del StudentUNet1CH4Heads (StudentPatchStage).
    # Ejemplo: /content/experiments/pipeline_model/01_binary_curve_cnn/student_1ch_4heads_boundary_rescue_final.pt
    student_patch_model_path: str = ""

    # URL de Redis para backup del trace (opcional, best-effort)
    # Ejemplo: redis://localhost:6379/0
    redis_url: str = ""

    s3_bucket: str = ""
    s3_prefix: str = "pipeline-ml"

    mongo_uri: str = ""
    mongo_database: str = "maia"
    mongo_collection: str = "pipeline_metrics"

    kafka_bootstrap_servers: str = ""
    kafka_topic_prefix: str = "pipeline-stage"
    kafka_topic: str = "pipeline-progress"
    lambda_function_name: str = ""


@dataclass
class PipelineConfig:
    debug: DebugFlags = field(default_factory=DebugFlags)
    routing: RoutingFlags = field(default_factory=RoutingFlags)
    paths: PipelinePaths = field(default_factory=PipelinePaths)

    @classmethod
    def _build_dataclass_from_dict(cls, dataclass_type, values: dict):
        """
        Helper: Create dataclass instance filtering kwargs to allowed fields.
        Ignores extra keys not defined in the dataclass to handle schema evolution.
        """
        from dataclasses import fields
        allowed_fields = {f.name for f in fields(dataclass_type)}
        filtered = {k: v for k, v in values.items() if k in allowed_fields}
        return dataclass_type(**filtered)

    @classmethod
    def from_json_file(cls, config_file: str | None) -> "PipelineConfig":
        if not config_file:
            return cls()

        path = Path(config_file)
        if not path.exists():
            raise FileNotFoundError(f"No existe el archivo de configuracion: {config_file}")

        data = json.loads(path.read_text(encoding="utf-8"))

        # Handle legacy Colab configs: migrate debug.write_local_artifacts -> routing.write_local_artifacts
        debug_cfg = data.get("debug", {})
        routing_cfg = data.get("routing", {})

        if "write_local_artifacts" in debug_cfg and "write_local_artifacts" not in routing_cfg:
            routing_cfg["write_local_artifacts"] = debug_cfg.pop("write_local_artifacts")

        # Use filtered construction to ignore unknown fields in legacy configs
        debug = cls._build_dataclass_from_dict(DebugFlags, debug_cfg)
        routing = cls._build_dataclass_from_dict(RoutingFlags, routing_cfg)
        paths_cfg = cls._build_dataclass_from_dict(PipelinePaths, data.get("paths", {}))

        return cls(debug=debug, routing=routing, paths=paths_cfg)
