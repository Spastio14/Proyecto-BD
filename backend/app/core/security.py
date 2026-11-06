import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, Request
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AccountInactive,
    AccountLinkMissing,
    AuthenticationRequired,
    DomainError,
    TokenExpired,
    TokenInvalid,
)
from app.db.session import get_session
from app.models.entities import Cliente, CuentaAcceso, Empleado


@dataclass(frozen=True, slots=True)
class Principal:
    persona_id: int
    origin: str

    @property
    def is_employee(self) -> bool:
        return self.origin == "EMPLEADO"


@dataclass(frozen=True, slots=True)
class VerifiedAuthIdentity:
    subject: str
    email: str


class IdentityVerificationUnavailable(DomainError):
    status_code = 503
    code = "identity_verification_unavailable"


class AuthenticationProvider(Protocol):
    def authenticate(self, request: Request, session: Session) -> Principal | None: ...


class TokenVerifier(Protocol):
    def verify(self, token: str) -> dict[str, Any]: ...


class SupabaseTokenVerifier:
    """Verifica firma y claims con las claves públicas JWKS del proyecto."""

    def __init__(self, *, project_url: str, project_ref: str, audience: str):
        self.issuer = f"{project_url.rstrip('/')}/auth/v1"
        self.project_ref = project_ref
        self.audience = audience
        self.jwks = PyJWKClient(f"{self.issuer}/.well-known/jwks.json", cache_keys=True)

    def verify(self, token: str) -> dict[str, Any]:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in {"RS256", "ES256"}:
            raise jwt.InvalidAlgorithmError("Algoritmo JWT no permitido")
        try:
            key = self.jwks.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError as exc:
            # Un fallo al descargar JWKS no demuestra que el token sea inválido.
            # Se conserva el cierre seguro, pero se permite al cliente reintentar.
            raise IdentityVerificationUnavailable(
                "No fue posible consultar temporalmente las claves de firma"
            ) from exc
        claims = jwt.decode(
            token,
            key,
            algorithms=[header["alg"]],
            audience=self.audience,
            issuer=self.issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        issuer_host = self.issuer.removeprefix("https://").split(".", 1)[0]
        if issuer_host != self.project_ref:
            raise jwt.InvalidIssuerError("El token pertenece a otro proyecto")
        return claims


class SupabaseAuthenticationProvider:
    def __init__(self, verifier: TokenVerifier):
        self.verifier = verifier

    def authenticate(self, request: Request, session: Session) -> Principal | None:
        token = bearer_token(request)
        if token is None:
            return None
        try:
            claims = self.verifier.verify(token)
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpired("La sesión venció; inicia sesión nuevamente") from exc
        except jwt.PyJWTError as exc:
            raise TokenInvalid("Token de acceso inválido") from exc
        try:
            subject = str(UUID(str(claims.get("sub", ""))))
        except ValueError as exc:
            raise TokenInvalid("Token sin sujeto verificable") from exc
        account = session.scalar(
            select(CuentaAcceso).where(
                CuentaAcceso.identificador_autenticacion == subject,
                CuentaAcceso.estado_cuenta == "ACTIVA",
            )
        )
        if account is None:
            linked = session.scalar(
                select(CuentaAcceso).where(CuentaAcceso.identificador_autenticacion == subject)
            )
            if linked is None:
                raise AccountLinkMissing(
                    "La identidad verificada aún no tiene un vínculo comercial"
                )
            raise AccountInactive("La cuenta local está suspendida o bloqueada")
        employee = session.get(Empleado, account.id_persona)
        if employee is not None and employee.estado_laboral == "ACTIVO":
            return Principal(account.id_persona, "EMPLEADO")
        customer = session.get(Cliente, account.id_persona)
        if customer is not None and customer.estado == "ACTIVO":
            return Principal(account.id_persona, "CLIENTE")
        raise AccountInactive("La persona vinculada no tiene un perfil activo")


class GuestCredentialSigner:
    def __init__(self, secret: str, *, max_age: int):
        self.max_age = max_age
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        self.cipher = Fernet(key)

    def issue(self, persona_id: int) -> str:
        payload = json.dumps({"persona_id": persona_id}, separators=(",", ":")).encode()
        return self.cipher.encrypt(payload).decode()

    def verify(self, credential: str) -> int:
        try:
            raw = self.cipher.decrypt(credential.encode(), ttl=self.max_age)
            data = json.loads(raw)
            persona_id = int(data["persona_id"])
            if persona_id <= 0:
                raise ValueError
            return persona_id
        except (InvalidToken, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise AuthenticationRequired("Credencial de invitado inválida o vencida") from exc


class GuestAuthenticationProvider:
    def __init__(self, signer: GuestCredentialSigner, cookie_name: str):
        self.signer = signer
        self.cookie_name = cookie_name

    def authenticate(self, request: Request, session: Session) -> Principal | None:
        credential = request.cookies.get(self.cookie_name)
        if credential is None:
            return None
        persona_id = self.signer.verify(credential)
        customer = session.get(Cliente, persona_id)
        if customer is None or customer.tipo_cliente != "INVITADO" or customer.estado != "ACTIVO":
            raise AuthenticationRequired("El perfil invitado ya no está activo")
        return Principal(persona_id, "CLIENTE")


class CompositeAuthenticationProvider:
    def __init__(self, *providers: AuthenticationProvider):
        self.providers = providers

    def authenticate(self, request: Request, session: Session) -> Principal | None:
        for provider in self.providers:
            principal = provider.authenticate(request, session)
            if principal is not None:
                return principal
        return None


class UnconfiguredAuthenticationProvider:
    """Cerrado por defecto cuando Supabase Auth no está configurado."""

    def authenticate(self, request: Request, session: Session) -> None:
        return None


def bearer_token(request: Request) -> str | None:
    value = request.headers.get("authorization")
    if not value:
        return None
    scheme, separator, token = value.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise AuthenticationRequired("Encabezado Authorization inválido")
    return token.strip()


def get_verified_auth_identity(request: Request) -> VerifiedAuthIdentity:
    verifier: TokenVerifier | None = getattr(request.app.state, "token_verifier", None)
    if verifier is None:
        raise IdentityVerificationUnavailable(
            "La verificación de identidades Supabase no está configurada"
        )
    token = bearer_token(request)
    if token is None:
        raise AuthenticationRequired("Se requiere una sesión Supabase verificada")
    try:
        claims = verifier.verify(token)
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpired("La sesión venció; solicita un enlace nuevo") from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalid("Token de acceso inválido") from exc
    try:
        subject = str(UUID(str(claims.get("sub", ""))))
    except ValueError as exc:
        raise TokenInvalid("Token sin sujeto verificable") from exc
    email = claims.get("email")
    if not isinstance(email, str) or not email.strip() or "@" not in email:
        raise TokenInvalid("La sesión no contiene un correo verificable")
    if claims.get("is_anonymous") is True:
        raise TokenInvalid("Una sesión anónima no puede completar este vínculo")
    return VerifiedAuthIdentity(subject=subject, email=email.strip().lower())


def get_principal(request: Request, session: Session = Depends(get_session)) -> Principal:
    principal = request.app.state.auth_provider.authenticate(request, session)
    if principal is None:
        raise AuthenticationRequired("Se requiere una identidad verificada")
    return principal
