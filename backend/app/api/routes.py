from fastapi import APIRouter, File, HTTPException, UploadFile

from app.ai import ExplanationCollection, explain_insights
from app.analysis import DatasetAnalysis, analyze_dataset
from app.config import settings
from app.ingestion import DatasetValidationError, load_dataset
from app.insights import InsightCollection, build_insights
from app.profiling import DatasetPreview, DatasetProfile, build_preview, profile_dataset
from app.quality import QualityReport, check_dataset_quality
from app.recipes import Recipe, RecipePreview, planned_columns, run_recipe
from app.store import DatasetLimit, Lineage, LineageEntry, StoredDataset, dataset_store
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
    return build_preview(dataset_id, dataset_store.frame_of(stored), limit)


@router.get("/datasets/{dataset_id}/analysis", response_model=DatasetAnalysis)
def get_analysis(dataset_id: str) -> DatasetAnalysis:
    stored = _require_dataset(dataset_id)
    return analyze_dataset(dataset_store.frame_of(stored), stored.profile)


@router.get("/datasets/{dataset_id}/charts", response_model=ChartCollection)
def get_charts(dataset_id: str) -> ChartCollection:
    stored = _require_dataset(dataset_id)
    frame = dataset_store.frame_of(stored)
    analysis = analyze_dataset(frame, stored.profile)
    return build_charts(frame, stored.profile, analysis)


@router.get("/datasets/{dataset_id}/insights", response_model=InsightCollection)
def get_insights(dataset_id: str) -> InsightCollection:
    stored = _require_dataset(dataset_id)
    frame = dataset_store.frame_of(stored)
    analysis = analyze_dataset(frame, stored.profile)
    charts = build_charts(frame, stored.profile, analysis)
    quality = check_dataset_quality(frame, stored.profile)
    return build_insights(stored.profile, analysis, quality, charts.charts)


@router.get("/datasets/{dataset_id}/explanations", response_model=ExplanationCollection)
def get_explanations(dataset_id: str) -> ExplanationCollection:
    """Plain-language readings of the findings, fetched separately.

    The dashboard renders without this, so a slow or missing model never holds up
    the numbers.
    """
    stored = _require_dataset(dataset_id)
    frame = dataset_store.frame_of(stored)
    analysis = analyze_dataset(frame, stored.profile)
    charts = build_charts(frame, stored.profile, analysis)
    quality = check_dataset_quality(frame, stored.profile)
    insights = build_insights(stored.profile, analysis, quality, charts.charts)
    return explain_insights(stored.profile, quality.score, insights.insights)


@router.get("/datasets/{dataset_id}/quality", response_model=QualityReport)
def get_quality(dataset_id: str) -> QualityReport:
    stored = _require_dataset(dataset_id)
    return check_dataset_quality(dataset_store.frame_of(stored), stored.profile)


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
