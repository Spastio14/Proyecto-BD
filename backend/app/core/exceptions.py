from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class AuthenticationRequired(DomainError):
    status_code = 401
    code = "authentication_required"


class TokenExpired(AuthenticationRequired):
    code = "token_expired"


class TokenInvalid(AuthenticationRequired):
    code = "token_invalid"


class AccountLinkMissing(DomainError):
    status_code = 404
    code = "account_link_missing"


class AccountInactive(DomainError):
    status_code = 403
    code = "account_inactive"


class PermissionDenied(DomainError):
    status_code = 403
    code = "permission_denied"


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class Conflict(DomainError):
    status_code = 409
    code = "conflict"


class InsufficientInventory(Conflict):
    code = "insufficient_inventory"


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "detail": exc.message},
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, __: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": "integrity_conflict",
                "detail": "La operación contradice la integridad de los datos",
            },
        )
