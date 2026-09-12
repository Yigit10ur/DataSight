from fastapi import APIRouter, File, HTTPException, UploadFile

from app.analysis import DatasetAnalysis, analyze_dataset
from app.config import settings
from app.ingestion import DatasetValidationError, load_dataset
from app.profiling import DatasetPreview, DatasetProfile, build_preview, profile_dataset
from app.store import StoredDataset, dataset_store
from app.visualization import ChartCollection, build_charts

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
    return _require_dataset(dataset_id).profile


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreview)
def get_preview(dataset_id: str, limit: int = 25) -> DatasetPreview:
    stored = _require_dataset(dataset_id)
    return build_preview(dataset_id, stored.frame, limit)


@router.get("/datasets/{dataset_id}/analysis", response_model=DatasetAnalysis)
def get_analysis(dataset_id: str) -> DatasetAnalysis:
    stored = _require_dataset(dataset_id)
    return analyze_dataset(stored.frame, stored.profile)


@router.get("/datasets/{dataset_id}/charts", response_model=ChartCollection)
def get_charts(dataset_id: str) -> ChartCollection:
    stored = _require_dataset(dataset_id)
    analysis = analyze_dataset(stored.frame, stored.profile)
    return build_charts(stored.frame, stored.profile, analysis)


def _require_dataset(dataset_id: str) -> StoredDataset:
    stored = dataset_store.get(dataset_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return stored
