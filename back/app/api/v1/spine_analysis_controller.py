import logging
import cv2
import numpy as np
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from app.schemas.pipeline_schema import PipelineClinicalResultDTO

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/analyze", response_model=PipelineClinicalResultDTO)
async def analyze_spine(
    file: UploadFile = File(..., description="Radiografía de columna"),
    nombre: str = Form(...),
    apellido_paterno: str = Form(...),
    edad: int = Form(...),
    peso: float = Form(...),
    sexo: str = Form(...),
    fecha: str = Form(...),
):
    """
    Ejecuta el pipeline ML completo para análisis de escoliosis.
    Devuelve predicciones clínicas, imágenes procesadas y métricas.
    """
    try:
        # 1. Leer imagen
        image_bytes = await file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        if image is None:
            raise HTTPException(status_code=400, detail="No se pudo decodificar la imagen")
        
        # 2. Construir assets string (ajusta las rutas a tus modelos)
        # Formato: NOMBRE|joblib1;joblib2;joblib3|recurso1;recurso2
        full_name = f"{apellido_paterno}_{nombre}"
        
        # Estas rutas deben apuntar a tus modelos entrenados
        cnn_curve_path = "/app/models/cnn_curve_binary.pt"
        student_path = "/app/models/student_unet_4heads.pt"
        clustering_path = "/app/models/clustering_gmm.joblib"
        
        full_assets = f"{full_name}|{cnn_curve_path};{student_path};{clustering_path}|"
        
        # 3. Configuración del pipeline
        config_file = "/app/config/pipeline_config.json"  # Ajusta según tu configuración
        
        # 4. Ejecutar pipeline
        from pipeline_ml.entrypoint import run_pipeline_entry
        
        result = run_pipeline_entry(
            image=image,
            full_assets=full_assets,
            config_file=config_file,
            request_id=None  # Se genera automáticamente
        )
        
        # 5. Construir respuesta
        if not result.get("ok", False):
            raise HTTPException(
                status_code=500, 
                detail=f"Pipeline falló: {result.get('message', 'Error desconocido')}"
            )
        
        outputs = result.get("outputs", {})
        clinical_result = outputs.get("clinical_result", {})
        
        # 6. Convertir a DTO
        response = PipelineClinicalResultDTO.from_pipeline_output(outputs)
        
        logger.info(
            f"Análisis completado: request_id={response.request_id}, "
            f"cobb_angle={response.predictions.cobb_angle_deg}°"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error en análisis de columna: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))