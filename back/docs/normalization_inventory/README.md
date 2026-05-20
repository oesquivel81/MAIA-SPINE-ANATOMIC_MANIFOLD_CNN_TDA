# Normalization Methods Inventory

Este documento lista los metodos involucrados en:
1. Leer perfiles desde `back/resources/NORMALIZATION_PROFILES`.
2. Usar esos perfiles para normalizar imagenes.
3. Ubicar donde se hace normalizacion dentro del notebook de Colab.

## 1) Lectura de perfiles (source: NORMALIZATION_PROFILES)

Archivo: `back/app/services/normalization_profile_loader.py`

### `NormalizationProfileLoader.__init__(settings, redis_component, mongo_component)`
- Entrada:
  - `settings: Settings`
  - `redis_component: RedisComponent`
  - `mongo_component: MongoComponent`
- Proceso:
  - Define `self._profiles_dir = back/resources/NORMALIZATION_PROFILES`.
  - Define `self._index_jsonl = normalization_profile_index.jsonl`.
- Salida:
  - Inicializa rutas y clientes para lectura/carga de perfiles.

### `NormalizationProfileLoader._read_profile_index_jsonl()`
- Entrada:
  - Sin argumentos externos.
  - Usa `self._index_jsonl`.
- Proceso:
  - Lee el JSONL linea por linea.
  - Convierte cada linea a `dict`.
- Salida:
  - `list[dict[str, Any]]` con los perfiles.
- Errores:
  - `FileNotFoundError` si no existe el indice.
  - `ValueError` si el indice esta vacio.

### `NormalizationProfileLoader.get_profiles(source=None)`
- Entrada:
  - `source: str | None` (`json`, `redis`, `mongo`).
- Proceso:
  - Si `json`: llama `_read_profile_index_jsonl()`.
  - Si `redis`: llama `_read_profiles_from_redis()`.
  - Si `mongo`: llama `_read_profiles_from_mongo()`.
- Salida:
  - `list[dict[str, Any]]` perfiles listos para normalizacion.

### `NormalizationProfileLoader.load_profiles_to_redis()`
- Entrada:
  - Sin argumentos externos.
- Proceso:
  - Lee indice JSONL con `_read_profile_index_jsonl()`.
  - Persiste perfiles en Redis.
- Salida:
  - `int`: cantidad de perfiles cargados.

### `NormalizationProfileLoader.load_profiles_to_mongo()`
- Entrada:
  - Sin argumentos externos.
- Proceso:
  - Lee indice JSONL con `_read_profile_index_jsonl()`.
  - Upsert por `patient_key` en Mongo.
- Salida:
  - `int`: cantidad de perfiles cargados.

### `NormalizationProfileLoader._read_profiles_from_redis()`
- Entrada:
  - Sin argumentos externos.
- Proceso:
  - Lee perfiles desde Redis.
  - Si no existen, ejecuta `load_profiles_to_redis()` (que lee JSONL).
- Salida:
  - `list[dict[str, Any]]`.

### `NormalizationProfileLoader._read_profiles_from_mongo()`
- Entrada:
  - Sin argumentos externos.
- Proceso:
  - Lee perfiles desde Mongo.
  - Si no existen, ejecuta `load_profiles_to_mongo()` (que lee JSONL).
- Salida:
  - `list[dict[str, Any]]`.

## 2) Uso de perfiles para normalizar

Archivo: `back/app/services/normalization_service.py`

### `NormalizationService.normalize_bytes(content, profile_source=None, compare_content=None, compare_profile_payload=None)`
- Entrada:
  - `content: bytes` (imagen).
  - `profile_source: str | None`.
  - `compare_content: bytes | None`.
  - `compare_profile_payload: dict | None`.
- Proceso:
  - Decodifica imagen y llama `_normalize_array(...)`.
- Salida:
  - `dict[str, Any]` con imagen normalizada, perfil usado, metricas y metadata.

### `NormalizationService.normalize_file_paths(image_path, profile_source=None, compare_image_path=None, compare_profile_json_path=None)`
- Entrada:
  - `image_path: str | Path`.
  - `profile_source: str | None`.
  - `compare_image_path: str | Path | None`.
  - `compare_profile_json_path: str | Path | None`.
- Proceso:
  - Lee bytes desde rutas y delega a `normalize_bytes(...)`.
- Salida:
  - `dict[str, Any]`.

### `NormalizationService.normalize_image(file, profile_source=None, compare_file=None, compare_profile_json=None)`
- Entrada:
  - `file: UploadFile`.
  - `profile_source: str | None`.
  - `compare_file: UploadFile | None`.
  - `compare_profile_json: UploadFile | None`.
- Proceso:
  - Lee uploads y delega a `normalize_bytes(...)`.
- Salida:
  - `dict[str, Any]`.

### `NormalizationService._normalize_array(image, profile_source=None, compare_image=None, compare_profile_payload=None)`
- Entrada:
  - `image: np.ndarray`.
  - `profile_source: str | None`.
  - `compare_image: np.ndarray | None`.
  - `compare_profile_payload: dict | None`.
- Proceso:
  - Calcula stats de entrada.
  - Llama `_get_profiles(...)` para obtener perfiles.
  - Selecciona perfil mas cercano con `_find_closest_profile(...)`.
  - Ejecuta pipeline con `_run_pipeline(...)`.
- Salida:
  - `dict[str, Any]` con:
    - `closest_profile_*`
    - `input_stats`, `output_stats`
    - `output_image_base64`
    - `runtime_metadata`
    - `comparison` (opcional)

### `NormalizationService._get_profiles(profile_source)`
- Entrada:
  - `profile_source: str`.
- Proceso:
  - Llama `self._profile_loader.get_profiles(profile_source)`.
- Salida:
  - `list[dict[str, Any]]`.

### `NormalizationService._find_closest_profile(input_stats, profiles)`
- Entrada:
  - `input_stats: dict[str, float]`.
  - `profiles: list[dict[str, Any]]`.
- Proceso:
  - Calcula distancia ponderada por metricas (`mean`, `std`, `median`, `p5`, `p95`, `aspect_ratio`).
- Salida:
  - `tuple[dict[str, Any], float]` = `(best_profile, best_distance)`.

## 3) Donde normaliza el notebook Colab

Archivo: `back/resources/colab/PIPELINE_COMPLETE_2_CNN_OLD_SHARDS_REGIONIDX_FROM_YLABEL_FAST_20E_BS64.ipynb`

Coincidencias clave encontradas:
- Linea 436276: `def robust_mad_normalize_array(img):`
- Linea 436297: `def robust_mad_normalize_image_for_inference(src_path, dst_path):`
- Linea 436411: llamada a `robust_mad_normalize_image_for_inference(dst_original, dst_norm)`
- Lineas 436429 y 436527: salida de manifiesto `rx_normalized_manifest.csv` del flujo de normalizacion.

Notas:
- No se detectaron referencias directas a la carpeta `NORMALIZATION_PROFILES` dentro de este notebook.
- La lectura de `NORMALIZATION_PROFILES` esta implementada en backend (`normalization_profile_loader.py`), no en este notebook.
