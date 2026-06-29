from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .api.deps import AuthApiError
from .routes.auth import router as auth_router
from .routes.projects import router as projects_router
from .routes.users import router as users_router

app = FastAPI(title="Katana Migration Engine")
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)


@app.exception_handler(AuthApiError)
async def auth_api_error_handler(_request: object, exc: AuthApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
