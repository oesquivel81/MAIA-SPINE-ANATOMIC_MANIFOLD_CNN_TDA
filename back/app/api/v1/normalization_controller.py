from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.container import get_normalization_service
from app.schemas.normalization_schema import NormalizationResponse
from app.services.normalization_service import NormalizationService

router = APIRouter()


@router.post("/image", response_model=NormalizationResponse)
async def normalize_image(
    file: UploadFile = File(...),
    profile_source: str | None = Form(None),
    compare_file: UploadFile | None = File(None),
    compare_profile_json: UploadFile | None = File(None),
    normalization_service: NormalizationService = Depends(get_normalization_service),
):
    return await normalization_service.normalize_image(
        file=file,
        profile_source=profile_source,
        compare_file=compare_file,
        compare_profile_json=compare_profile_json,
    )
