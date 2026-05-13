from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.container import get_file_service
from app.services.file_service import FileService

router = APIRouter()


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
):
    return await file_service.upload_file(file)


@router.get("/{file_id}")
async def get_file_metadata(
    file_id: str,
    file_service: FileService = Depends(get_file_service),
):
    data = await file_service.get_file_metadata(file_id)
    if not data:
        raise HTTPException(status_code=404, detail="File metadata not found")
    return data
