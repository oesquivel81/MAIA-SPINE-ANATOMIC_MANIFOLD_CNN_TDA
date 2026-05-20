from pydantic import BaseModel


class PatientUploadResponse(BaseModel):
    id: str
    nombre: str
    apellido_paterno: str
    edad: int
    peso: float
    sexo: str
    fecha: str
    s3_bucket: str
    s3_key: str
    image_url: str | None
    created_at: str
