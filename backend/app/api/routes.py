from pathlib import Path
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.analysis import DatasetAnalysis
from app.config import settings
from app.dashboard import DashboardAnalysis, dashboard_cache
from app.ingestion import DatasetValidationError, load_dataset
from app.insights import InsightCollection
from app.profiling import DatasetPreview, DatasetProfile, build_preview, profile_dataset
from app.quality import QualityReport
from app.recipes import Recipe, RecipePreview, planned_columns, run_recipe
from app.store import (
    DatasetLimit,
    Lineage,
    LineageEntry,
    StoredDataset,
    dataset_store,
    steps_phrase,
)
from app.visualization import ChartCollection

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@router.post("/upload", response_model=DatasetProfile)
async def upload(file: UploadFile = File(...)) -> DatasetProfile:
    # Read at most the limit plus one sentinel byte, never the entire untrusted
    # file. UploadFile itself is spooled by the multipart parser before this route.
    content = bytearray()
    try:
        while True:
            chunk = await file.read(min(64 * 1024, settings.max_upload_bytes - len(content) + 1))
            if not chunk:
                break
            if len(content) + len(chunk) > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds the upload limit of {settings.max_upload_bytes} bytes.",
                )
            content.extend(chunk)
        frame = load_dataset(file.filename or "", content, settings.max_upload_bytes)
    except DatasetValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        await file.close()

    dataset_id = dataset_store.new_id()
    profile = profile_dataset(dataset_id, file.filename or "dataset", frame)
    try:
        dataset_store.add(dataset_id, profile.filename, frame, profile)
    except DatasetLimit as limit:
        raise HTTPException(status_code=409, detail=str(limit)) from limit
    return profile


@router.get("/datasets/{dataset_id}/profile", response_model=DatasetProfile)
def get_profile(dataset_id: str) -> DatasetProfile:
    return _require_dataset(dataset_id).profile


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreview)
def get_preview(dataset_id: str, limit: int = 25) -> DatasetPreview:
    stored = _require_dataset(dataset_id)
    return build_preview(dataset_id, dataset_store.frame_of(stored), limit)


@router.get("/datasets/{dataset_id}/analysis", response_model=DatasetAnalysis)
def get_analysis(dataset_id: str) -> DatasetAnalysis:
    stored = _require_dataset(dataset_id)
    return _dashboard(stored).analysis


@router.get("/datasets/{dataset_id}/charts", response_model=ChartCollection)
def get_charts(dataset_id: str) -> ChartCollection:
    stored = _require_dataset(dataset_id)
    return _dashboard(stored).charts


@router.get("/datasets/{dataset_id}/insights", response_model=InsightCollection)
def get_insights(dataset_id: str) -> InsightCollection:
    stored = _require_dataset(dataset_id)
    return _dashboard(stored).insights


@router.get("/datasets/{dataset_id}/quality", response_model=QualityReport)
def get_quality(dataset_id: str) -> QualityReport:
    stored = _require_dataset(dataset_id)
    return _dashboard(stored).quality


@router.post("/datasets/{dataset_id}/recipe/preview", response_model=RecipePreview)
def preview_recipe(dataset_id: str, recipe: Recipe, limit: int = 25) -> RecipePreview:
    """Run a recipe and throw the result away.

    This is what the interface calls while a reader is still building, so it stores
    nothing and never creates a dataset. A refused step comes back as part of a
    normal response together with the rows the accepted steps left, so the reader
    keeps their place while they fix it.
    """
    stored = _require_dataset(dataset_id)
    frame = dataset_store.frame_of(stored)
    run = run_recipe(frame, planned_columns(stored.profile.column_schemas), recipe)

    return RecipePreview(
        dataset_id=dataset_id,
        source_rows=len(frame),
        columns=run.columns,
        preview=build_preview(dataset_id, run.frame, limit),
        reports=run.reports,
        analysis=run.analysis,
        refusal=run.refusal,
    )


@router.post("/datasets/{dataset_id}/recipe/apply", response_model=DatasetProfile)
def apply_recipe(dataset_id: str, recipe: Recipe) -> DatasetProfile:
    """Keep a recipe's result as a dataset of its own.

    It answers with a profile, exactly as an upload does, because from here on the
    result is a dataset like any other: every other endpoint takes its id and needs
    to know nothing about where it came from.
    """
    stored = _require_dataset(dataset_id)
    if not recipe.steps:
        raise HTTPException(status_code=400, detail="A recipe with no steps changes nothing.")
    if recipe.analyze is not None:
        # An analysis answers with a finding, not a table, so there is nothing here
        # to keep as a dataset. The rows it was computed from can be kept instead.
        raise HTTPException(
            status_code=400,
            detail=(
                "An analysis answers with a finding rather than a table. Remove it to save "
                "the rows it was computed from."
            ),
        )

    frame = dataset_store.frame_of(stored)
    run = run_recipe(frame, planned_columns(stored.profile.column_schemas), recipe)
    if run.refusal is not None:
        raise HTTPException(status_code=400, detail=run.refusal.model_dump())
    if run.frame.empty:
        raise HTTPException(
            status_code=400,
            detail="This recipe leaves no rows, and there is nothing to profile in that.",
        )

    derived_id = dataset_store.new_id()
    profile = profile_dataset(
        derived_id, dataset_store.derived_name(stored, len(recipe.steps)), run.frame
    )
    try:
        dataset_store.add_derived(derived_id, stored, recipe, run.frame, profile)
    except DatasetLimit as limit:
        raise HTTPException(status_code=409, detail=str(limit)) from limit
    return profile


# Written out in slices rather than as one string, so that exporting a large file
# does not need a second copy of it in memory before the first byte is sent.
EXPORT_CHUNK_ROWS = 5_000


def _csv_chunks(frame: pd.DataFrame):
    yield frame.head(0).to_csv(index=False)
    for start in range(0, len(frame), EXPORT_CHUNK_ROWS):
        yield frame.iloc[start : start + EXPORT_CHUNK_ROWS].to_csv(index=False, header=False)


def _download_name(stored: StoredDataset, step_count: int) -> str:
    """Name the file after the one it came from and how far it has come.

    The dataset's own name reads as provenance — "orders.csv (5 steps)" — which is
    right on a screen and wrong on a disk. This turns it back into a filename.
    """
    root = dataset_store.lineage(stored)[0]
    stem = Path(root.filename).stem or "dataset"
    steps = dataset_store.total_steps(stored, step_count)
    return f"{stem}.csv" if steps == 0 else f"{stem} ({steps_phrase(steps)}).csv"


def _attachment(name: str) -> str:
    """A Content-Disposition that survives a name the ASCII header cannot hold."""
    plain = "".join(
        character for character in name if character.isascii() and character not in '"\\\r\n'
    )
    return f"attachment; filename=\"{plain or 'dataset.csv'}\"; filename*=UTF-8''{quote(name)}"


@router.post("/datasets/{dataset_id}/recipe/export")
def export_recipe(dataset_id: str, recipe: Recipe) -> StreamingResponse:
    """Send the rows a recipe produces as a CSV, storing nothing.

    An empty recipe exports the dataset as it stands, which is what the button does
    when a reader has not shaped anything. A terminal analysis is dropped rather than
    run: a CSV is rows, and a finding is not one.
    """
    stored = _require_dataset(dataset_id)
    frame = dataset_store.frame_of(stored)
    rows_only = Recipe(steps=recipe.steps)
    run = run_recipe(frame, planned_columns(stored.profile.column_schemas), rows_only)
    if run.refusal is not None:
        raise HTTPException(status_code=400, detail=run.refusal.model_dump())

    return StreamingResponse(
        _csv_chunks(run.frame),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": _attachment(_download_name(stored, len(recipe.steps)))},
    )


@router.get("/datasets/{dataset_id}/lineage", response_model=Lineage)
def get_lineage(dataset_id: str) -> Lineage:
    """Where this dataset came from, the uploaded file first."""
    stored = _require_dataset(dataset_id)
    return Lineage(
        dataset_id=dataset_id,
        chain=[
            LineageEntry(
                dataset_id=dataset.dataset_id,
                filename=dataset.filename,
                rows=dataset.profile.rows,
                columns=dataset.profile.columns,
                recipe=dataset.recipe,
            )
            for dataset in dataset_store.lineage(stored)
        ],
    )


def _require_dataset(dataset_id: str) -> StoredDataset:
    stored = dataset_store.get(dataset_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return stored


def _dashboard(stored: StoredDataset) -> DashboardAnalysis:
    """Compute once for this immutable dataset and reject a result that expired."""
    frame = dataset_store.frame_of(stored)
    shaped = dataset_store.provenance(stored)
    result = dashboard_cache.get_or_compute(
        stored.dataset_id,
        frame,
        stored.profile,
        shaped,
        retain=lambda: dataset_store.get(stored.dataset_id) is stored,
    )
    if dataset_store.get(stored.dataset_id) is not stored:
        dashboard_cache.remove(stored.dataset_id)
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return result
