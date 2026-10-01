import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.accounts import account_store
from app.api.auth import router as auth_router
from app.api.routes import router
from app.config import settings
from app.store import DatasetNotFound, dataset_store


async def expire_datasets() -> None:
    while True:
        await asyncio.sleep(60)
        await asyncio.to_thread(dataset_store.expire)
        await asyncio.to_thread(account_store.purge_expired_sessions)


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


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def refuse_cross_site_writes(request: Request, call_next):
    """Turn away a write that a page from another origin started.

    The session cookie is SameSite=Lax, which already keeps it off most of these.
    This also covers what Lax allows: a sibling subdomain counts as the same site.
    Browsers send Origin with every cross-origin write; a request without one did
    not come from another site's page.
    """
    origin = request.headers.get("origin")
    # The API's own origin is allowed too, for the interactive docs it serves.
    own = f"{request.url.scheme}://{request.url.netloc}"
    if (
        request.method in UNSAFE_METHODS
        and origin
        and origin != own
        and origin not in settings.cors_origins
    ):
        return JSONResponse(status_code=403, content={"detail": "Cross-site request refused."})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # The session cookie has to travel with requests from the frontend's origin
    # when it differs from the API's, as it does in local development.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(router, prefix="/api")
