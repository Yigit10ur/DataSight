from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.ingestion import DatasetValidationError, load_dataset
from app.profiling import DatasetProfile, profile_dataset
from app.store import dataset_store

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@router.post("/upload", response_model=DatasetProfile)
async def upload(file: UploadFile = File(...)) -> DatasetProfile:
    content = await file.read()
    try:
        frame = load_dataset(file.filename or "", content, settings.max_upload_bytes)
    except DatasetValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    dataset_id = dataset_store.new_id()
    profile = profile_dataset(dataset_id, file.filename or "dataset", frame)
    dataset_store.add(dataset_id, profile.filename, frame, profile)
    return profile


@router.get("/datasets/{dataset_id}/profile", response_model=DatasetProfile)
def get_profile(dataset_id: str) -> DatasetProfile:
    stored = dataset_store.get(dataset_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return stored.profile
