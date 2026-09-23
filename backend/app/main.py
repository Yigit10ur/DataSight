import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import settings
from app.store import DatasetNotFound, dataset_store


async def expire_datasets() -> None:
    while True:
        await asyncio.sleep(60)
        await asyncio.to_thread(dataset_store.expire)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(expire_datasets())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if settings.api_docs else None,
    redoc_url="/redoc" if settings.api_docs else None,
    openapi_url="/openapi.json" if settings.api_docs else None,
)


@app.exception_handler(DatasetNotFound)
async def dataset_not_found(request: Request, error: DatasetNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Dataset not found."})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # The API uses no cookies or auth headers, so browsers get no credentialed access.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
