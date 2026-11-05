from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

from app.core.exceptions import AuthenticationRequired


@dataclass(frozen=True, slots=True)
class Principal:
    persona_id: int
    origin: str

    @property
    def is_employee(self) -> bool:
        return self.origin == "EMPLEADO"


class AuthenticationProvider(Protocol):
    def authenticate(self, request: Request) -> Principal | None: ...


class UnconfiguredAuthenticationProvider:
    """Fase 2: cerrado hasta integrar Supabase Auth en Fase 3."""

    def authenticate(self, request: Request) -> None:
        return None


def get_principal(request: Request) -> Principal:
    principal = request.app.state.auth_provider.authenticate(request)
    if principal is None:
        raise AuthenticationRequired("Se requiere una identidad verificada")
    return principal
