from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.deps import AuthApiError
from .config import get_settings
from .routes.auth import router as auth_router
from .routes.projects import router as projects_router
from .routes.runs import router as runs_router
from .routes.analysis import router as analysis_router
from .routes.lookup import router as lookup_router
from .routes.sources import router as sources_router
from .routes.slice_approval import router as slice_approval_router
from .routes.users import router as users_router

app = FastAPI(title="Katana Migration Engine")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(runs_router)
app.include_router(analysis_router)
app.include_router(lookup_router)
app.include_router(sources_router)
app.include_router(slice_approval_router)


@app.exception_handler(AuthApiError)
async def auth_api_error_handler(_request: object, exc: AuthApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
