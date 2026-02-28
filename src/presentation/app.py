from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.presentation.api.v1.health import router as health_router


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

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health_router, prefix="/api/v1")

    return app
