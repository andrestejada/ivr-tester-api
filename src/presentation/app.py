from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.presentation.api.v1.auth import router as auth_router
from src.presentation.api.v1.health import router as health_router
from src.presentation.api.v1.ivr_architectures import router as ivr_architectures_router
from src.presentation.api.v1.test_cases import router as test_cases_router
from src.presentation.api.v1.test_executions import router as test_executions_router
from src.presentation.api.v1.analytics import router as analytics_router
from src.presentation.api.v1.webhooks.twilio_voice import router as twilio_webhook_router
from src.presentation.api.v1.websockets.call_stream import router as call_stream_router
from src.presentation.api.v1.websockets.execution_stream import router as execution_stream_router
from src.presentation.exception_handlers import register_exception_handlers
from src.infrastructure.logger import setup_logger


def create_app() -> FastAPI:
    # Setup central logger
    setup_logger()

    app = FastAPI(
        title="IVR Tester API",
        description="Motor de orquestación de pruebas automatizadas para IVRs.",
        version="0.1.0",
    )

    # ── Exception Handlers ───────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── CORS ─────────────────────────────────────────────────────────────────
    # IMPORTANT: CORS middleware MUST be added last to ensure it wraps all responses
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # frontend dev
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(ivr_architectures_router, prefix="/api/v1")
    app.include_router(test_cases_router, prefix="/api/v1")
    app.include_router(test_executions_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    
    # Webhooks (sin prefix, rutas absolutas)
    app.include_router(twilio_webhook_router)
    
    # WebSockets (sin prefix, rutas absolutas)
    app.include_router(call_stream_router)
    app.include_router(execution_stream_router)

    return app
