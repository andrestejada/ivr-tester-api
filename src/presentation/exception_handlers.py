from fastapi import Request
from fastapi.responses import JSONResponse

from src.application.exceptions import (
    ApplicationException,
    BusinessValidationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


async def business_validation_handler(
    request: Request, exc: BusinessValidationError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def application_exception_handler(
    request: Request, exc: ApplicationException
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


def register_exception_handlers(app) -> None:
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(ConflictError, conflict_handler)
    app.add_exception_handler(ForbiddenError, forbidden_handler)
    app.add_exception_handler(BusinessValidationError, business_validation_handler)
    app.add_exception_handler(ApplicationException, application_exception_handler)
