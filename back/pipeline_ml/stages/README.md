# pipeline_ml / stages

Directorio con los stages del pipeline ML de MAIA-SPINE.  
Cada stage implementa `PipelineStage` (base.py) y expone un único método `run(payload, context, logger) → payload`.

---

## PreprocessingStage  (`preprocessing.py`)

### Qué hace

1. **Carga el índice JSONL de perfiles** de normalización (`normalization_profile_index.jsonl`).  
   Orden de búsqueda:
   - `paths.normalization_profile_jsonl` del config (override explícito)
   - `.jsonl` en los `resource_paths` del `AssetBundle`
   - `back/resources/NORMALIZATION_PROFILES/normalization_profile_index.jsonl` (ruta relativa al paquete — siempre disponible si el repo está clonado)
   - Redis: clave `normalization_profiles:index:v1` (fallback)

2. **Computa estadísticas** de la imagen de entrada: min, max, mean, std, median, p1, p5, p95, p99, aspect_ratio.

3. **Selecciona el perfil más cercano** vía `DynamicNormalizationEngine.select_closest_profile(input_stats, profiles)`.

4. **Normaliza la imagen** con `DynamicNormalizationEngine.run()` (intensidad + resize al `target_long_side` del perfil).  
   La llamada async se ejecuta en un `ThreadPoolExecutor(max_workers=1)` para compatibilidad con Python 3.12 / Jupyter / Colab (donde ya hay un event loop activo).

5. **Visualización opcional** (`debug.plots_show = True`):
   - `_show_image`: imagen de entrada en escala de grises con estadísticas.
   - `_compare_images`: grid 1×2 entrada vs salida con estadísticas completas.

6. **Guarda la imagen normalizada** en `outputs_dir/normalized_image.png`.

7. **Construye el trace JSON** con el formato exacto de `N_1_normalization_profile.json`:

   ```
   patient_id, normalization_mode, normalization_p_low/high,
   normalization_mask_source, original_shape, resized_shape,
   final_image_shape, standardize_long_side, target_long_side,
   scale_x, scale_y, processed_mask_path,
   image_before_norm_stats, image_after_norm_stats,
   + closest_profile_key, closest_profile_distance, request_id
   ```

8. **Persiste el trace** en tres destinos:
   - `outputs_dir/normalization_trace.json` — artefacto del pipeline (siempre)
   - `patient_json_profiles_dir/{patient_id}_{request_id}_normalization_profile.json` — referencia persistente (siempre)
   - Redis key `normalization_applied:{patient_id}:{request_id}` con TTL 7 días (best-effort, solo si `paths.redis_url` está configurado)

### Artefactos que produce en el payload

| Clave                        | Tipo             | Descripción                                    |
|------------------------------|------------------|------------------------------------------------|
| `image`                      | `np.ndarray`     | Imagen normalizada (reemplaza la original)     |
| `preprocessed`               | `bool`           | `True` si el stage completó sin error          |
| `normalized_image_path`      | `str`            | Ruta absoluta del PNG guardado                 |
| `normalization_trace`        | `dict`           | Trace completo en formato N_1                  |
| `normalization_trace_path`   | `str`            | Ruta al `normalization_trace.json` en outputs  |
| `normalization_profile_path` | `str \| None`    | Ruta al JSON persistido en `patient_json_profiles_dir` |

### Configuración relevante

```python
# config.json / CONFIG_DEBUG
{
    "debug": {
        "plots_show": True    # activa _show_image y _compare_images
    },
    "paths": {
        "normalization_profile_jsonl": "",          # override de ruta; vacío = usa canónica
        "patient_json_profiles_dir": "resources/NORMALIZATION_PROFILES/patient_json_profiles",
        "redis_url": ""                             # vacío = Redis desactivado
    }
}
```

---

## Pendiente — Integración con Redis / MongoDB / S3

Los tres servicios están **arquitecturados pero no conectados** en el stage.  
A continuación el estado exacto y lo que falta en cada uno.

### Redis

**Estado actual**  
- Conexión síncrona via `redis.from_url()` (librería `redis==5.x`).  
- Guarda el trace JSON con TTL 7 días en `normalization_applied:{patient_id}:{request_id}`.  
- Si `redis_url` está vacío o la conexión falla, el stage continúa sin error (best-effort).

**Lo que falta**  
- [ ] Guardar también el índice JSONL de perfiles en Redis (`normalization_profiles:index:v1`) para que el fallback de `_load_profiles` sea útil en entornos sin acceso al filesystem.  
- [ ] Un script/task de carga inicial que lea el JSONL local y lo publique en Redis (necesario al arrancar el backend en EKS).  
- [ ] En el backend FastAPI: el `RedisComponent` existente debería ser inyectado al pipeline en lugar de crear una conexión directa desde el stage (evitar múltiples sockets por request).

### MongoDB

**Estado actual**  
- El stage **no escribe directamente en Mongo**. El trace se persiste como JSON en disco (`patient_json_profiles_dir`).  
- `NormalizationTraceabilityService` (en `normalization_stage/traceability.py`) sí tiene la lógica para escribir en Mongo, pero sus imports de `app/` están bajo `TYPE_CHECKING` para no romper el entorno Colab.

**Lo que falta**  
- [ ] En la ruta FastAPI (`/api/pipeline`): tras completar el pipeline, llamar a `NormalizationTraceabilityService.save_trace(trace, mongo_component)` para persistir en la colección `normalization_traces`.  
- [ ] Definir schema Pydantic / índices Mongo para el trace (al menos índice en `patient_id` + `request_id`).  
- [ ] El stage podría recibir un flag `write_metrics_to_mongo` (ya existe en `RoutingFlags`) y, si está activo, hacer la escritura directa usando `motor` en el contexto async de FastAPI (nunca desde Colab).

### S3

**Estado actual**  
- La imagen normalizada se guarda **solo en disco local** (`outputs_dir/normalized_image.png`).  
- `RoutingFlags.write_outputs_to_s3` existe en el config pero el stage no lo evalúa.

**Lo que falta**  
- [ ] Leer `context.metadata["write_outputs_to_s3"]` (ya se pasa desde `entrypoint.py` via `RoutingFlags`).  
- [ ] Si es `True`, subir `normalized_image.png` + `normalization_trace.json` a S3 usando `S3Component` (disponible en el contexto FastAPI).  
- [ ] En entorno Colab: omitir S3 siempre (`colab_mode = True` → `write_outputs_to_s3 = False`).  
- [ ] Definir la ruta S3 destino, sugerencia: `{s3_prefix}/patients/{patient_id}/{request_id}/normalized_image.png`.

---

## Guía de activación por entorno

| Entorno     | Redis | Mongo | S3  | plots_show |
|-------------|-------|-------|-----|------------|
| Colab debug | ❌    | ❌    | ❌  | ✅          |
| Local dev   | ✅    | ❌    | ❌  | opcional   |
| EKS prod    | ✅    | ✅    | ✅  | ❌          |
