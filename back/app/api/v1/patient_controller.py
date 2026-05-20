from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.container import get_patient_service
from app.schemas.patient_schema import PatientUploadResponse
from app.services.patient_service import PatientService

router = APIRouter()


@router.post("", response_model=PatientUploadResponse)
async def upload_patient(
    file: UploadFile = File(..., description="Imagen del paciente"),
    nombre: str = Form(..., description="Nombre del paciente"),
    apellido_paterno: str = Form(..., description="Apellido paterno del paciente"),
    edad: int = Form(..., description="Edad del paciente"),
    peso: float = Form(..., description="Peso del paciente en kg"),
    sexo: str = Form(..., description="Sexo del paciente (M/F)"),
    fecha: str = Form(..., description="Fecha en formato YYYY-MM-DD"),
    patient_service: PatientService = Depends(get_patient_service),
):
    return await patient_service.upload_patient_image(
        file=file,
        nombre=nombre,
        apellido_paterno=apellido_paterno,
        edad=edad,
        peso=peso,
        sexo=sexo,
        fecha=fecha,
    )
