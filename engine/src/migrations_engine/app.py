from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .api.deps import AuthApiError
from .config import get_settings
from .routes.auth import router as auth_router
from .routes.projects import router as projects_router
from .routes.runs import router as runs_router
from .routes.analysis import router as analysis_router
from .routes.gates import router as gates_router
from .routes.codegen import router as codegen_router
from .routes.mapping import router as mapping_router
from .routes.mapping_snapshots import router as mapping_snapshots_router
from .routes.lookup import router as lookup_router
from .routes.impact import router as impact_router
from .routes.fibers import router as fibers_router
from .routes.fibers import feeds_router as fiber_analysis_router
from .routes.reconciliation import router as reconciliation_router
from .routes.feeds import router as feeds_router
from .routes.feed_slice_approval import router as feed_slice_approval_router
from .routes.users import router as users_router


def _validate_runtime_settings(settings: object) -> None:
    if os.environ.get("KATANA_ENV", "").lower() != "production":
        return
    if getattr(settings, "jwt_secret", None) == "dev-only-change-me":
        raise RuntimeError("Production JWT secret must not use the dev default.")


app = FastAPI(title="Katana Migration Engine")

_settings = get_settings()
_validate_runtime_settings(_settings)
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
app.include_router(gates_router)
app.include_router(codegen_router)
app.include_router(mapping_router)
app.include_router(mapping_snapshots_router)
app.include_router(lookup_router)
app.include_router(impact_router)
app.include_router(fibers_router)
app.include_router(fiber_analysis_router)
app.include_router(reconciliation_router)
app.include_router(feeds_router)
app.include_router(feed_slice_approval_router)


@app.exception_handler(AuthApiError)
async def auth_api_error_handler(_request: object, exc: AuthApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_request: object, _exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Invalid request body."}},
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
