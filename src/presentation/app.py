from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.presentation.api.v1.auth import router as auth_router
from src.presentation.api.v1.health import router as health_router
from src.presentation.api.v1.ivr_architectures import router as ivr_architectures_router
from src.presentation.api.v1.test_cases import router as test_cases_router
from src.presentation.exception_handlers import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="IVR Tester API",
        description="Motor de orquestación de pruebas automatizadas para IVRs.",
        version="0.1.0",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # frontend dev
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception Handlers ───────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(ivr_architectures_router, prefix="/api/v1")
    app.include_router(test_cases_router, prefix="/api/v1")

    return app
