from fastapi import Request
from fastapi.responses import JSONResponse

from src.application.exceptions import (
    ApplicationException,
    BusinessValidationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    logger.warning(f"NotFoundError: {exc}")
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    logger.warning(f"ConflictError: {exc}")
    return JSONResponse(status_code=409, content={"detail": str(exc)})


async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
    logger.warning(f"ForbiddenError: {exc}")
    return JSONResponse(status_code=403, content={"detail": str(exc)})


async def business_validation_handler(
    request: Request, exc: BusinessValidationError
) -> JSONResponse:
    logger.warning(f"BusinessValidationError: {exc}")
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def application_exception_handler(
    request: Request, exc: ApplicationException
) -> JSONResponse:
    logger.warning(f"ApplicationException: {exc}")
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error(f"Unhandled Exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500, 
        content={"detail": "Internal Server Error"}
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(ConflictError, conflict_handler)
    app.add_exception_handler(ForbiddenError, forbidden_handler)
    app.add_exception_handler(BusinessValidationError, business_validation_handler)
    app.add_exception_handler(ApplicationException, application_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
