import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, NoReturn, Protocol
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
    IdentityVerificationUnavailable,
    TokenAlgorithmUnsupported,
    TokenAudienceInvalid,
    TokenExpired,
    TokenInvalid,
    TokenIssuerInvalid,
    TokenSigningKeyNotFound,
)
from app.db.session import get_session
from app.models.entities import Cliente, CuentaAcceso, Empleado

logger = logging.getLogger(__name__)


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


class AuthenticationProvider(Protocol):
    def authenticate(self, request: Request, session: Session) -> Principal | None: ...


class TokenVerifier(Protocol):
    def verify(self, token: str) -> dict[str, Any]: ...


class UserTokenValidator(Protocol):
    def validate_access_token(self, *, access_token: str) -> dict[str, Any]: ...


class SupabaseTokenVerifier:
    """Verifica JWT asimétricos con JWKS y HS256 con Supabase Auth."""

    def __init__(
        self,
        *,
        project_url: str,
        project_ref: str,
        audience: str,
        user_token_validator: UserTokenValidator | None = None,
    ):
        self.issuer = f"{project_url.rstrip('/')}/auth/v1"
        self.project_ref = project_ref
        self.audience = audience
        self.user_token_validator = user_token_validator
        self.jwks = PyJWKClient(f"{self.issuer}/.well-known/jwks.json", cache_keys=True)

    def verify(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            self._reject("malformed_header", "unknown", None, TokenInvalid("Token malformado"), exc)
        algorithm = header.get("alg")
        kid = header.get("kid")
        if not isinstance(algorithm, str):
            self._reject(
                "missing_algorithm",
                "unknown",
                kid,
                TokenAlgorithmUnsupported("El token no declara un algoritmo válido"),
            )
        if algorithm == "HS256":
            return self._verify_hs256(token, kid)
        if algorithm not in {"RS256", "ES256"}:
            self._reject(
                "unsupported_algorithm",
                algorithm,
                kid,
                TokenAlgorithmUnsupported("El algoritmo del token no está permitido"),
            )
        if not isinstance(kid, str) or not kid.strip():
            self._reject(
                "missing_kid",
                algorithm,
                kid,
                TokenSigningKeyNotFound("El token no identifica una clave pública"),
            )
        try:
            key = self.jwks.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError as exc:
            self._reject(
                "jwks_connection_error",
                algorithm,
                kid,
                IdentityVerificationUnavailable(
                    "No fue posible consultar temporalmente las claves de firma"
                ),
                exc,
            )
        except jwt.PyJWKClientError as exc:
            self._reject(
                "signing_key_not_found",
                algorithm,
                kid,
                TokenSigningKeyNotFound(
                    "La clave pública indicada por el token no está disponible"
                ),
                exc,
            )
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=self.audience,
                issuer=self.issuer,
                leeway=30,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            logger.warning(
                "Diagnóstico JWT: exception_type=%s",
                type(exc).__name__,
            )
            self._raise_claim_error(exc, algorithm, kid)
        issuer_host = self.issuer.removeprefix("https://").split(".", 1)[0]
        if issuer_host != self.project_ref:
            self._reject(
                "project_ref_mismatch",
                algorithm,
                kid,
                TokenIssuerInvalid("La configuración apunta a otro proyecto Supabase"),
            )
        self._success("jwks", algorithm, kid)
        return claims

    def _verify_hs256(self, token: str, kid: object) -> dict[str, Any]:
        algorithm = "HS256"
        try:
            claims = jwt.decode(
                token,
                key="",
                algorithms=[algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "verify_signature": False,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "require": ["exp", "iat", "sub", "iss", "aud"],
                },
            )
        except jwt.PyJWTError as exc:
            self._raise_claim_error(exc, algorithm, kid)
        if self.user_token_validator is None:
            self._reject(
                "hs256_validator_unconfigured",
                algorithm,
                kid,
                IdentityVerificationUnavailable(
                    "La validación remota de sesiones HS256 no está configurada"
                ),
            )
        try:
            identity = self.user_token_validator.validate_access_token(access_token=token)
        except TokenExpired as exc:
            self._reject(
                "expired",
                algorithm,
                kid,
                TokenExpired(exc.message),
                exc,
            )
        except IdentityVerificationUnavailable as exc:
            self._reject(
                "auth_user_connection_error",
                algorithm,
                kid,
                IdentityVerificationUnavailable(exc.message),
                exc,
            )
        except TokenInvalid as exc:
            self._reject(
                "auth_user_rejected",
                algorithm,
                kid,
                TokenInvalid(exc.message),
                exc,
            )
        if not isinstance(identity, dict):
            self._reject(
                "auth_user_response_invalid",
                algorithm,
                kid,
                IdentityVerificationUnavailable(
                    "Supabase devolvió una identidad incompatible"
                ),
            )
        remote_subject = identity.get("id")
        if not isinstance(remote_subject, str) or remote_subject != str(claims.get("sub", "")):
            self._reject(
                "hs256_subject_mismatch",
                algorithm,
                kid,
                TokenInvalid("Supabase devolvió una identidad distinta a la sesión"),
            )
        remote_email = identity.get("email")
        token_email = claims.get("email")
        if (
            isinstance(remote_email, str)
            and isinstance(token_email, str)
            and remote_email.strip().lower() != token_email.strip().lower()
        ):
            self._reject(
                "hs256_email_mismatch",
                algorithm,
                kid,
                TokenInvalid("Supabase devolvió una identidad distinta a la sesión"),
            )
        if isinstance(remote_email, str):
            claims["email"] = remote_email.strip().lower()
        self._success("auth_user_endpoint", algorithm, kid)
        return claims

    def _raise_claim_error(
        self, exc: jwt.PyJWTError, algorithm: str, kid: object
    ) -> NoReturn:
        if isinstance(exc, jwt.ExpiredSignatureError):
            self._reject(
                "expired",
                algorithm,
                kid,
                TokenExpired("La sesión venció; inicia sesión nuevamente"),
                exc,
            )
        if isinstance(exc, jwt.InvalidIssuerError):
            self._reject(
                "issuer_invalid",
                algorithm,
                kid,
                TokenIssuerInvalid("El token pertenece a otro emisor"),
                exc,
            )
        if isinstance(exc, jwt.InvalidAudienceError):
            self._reject(
                "audience_invalid",
                algorithm,
                kid,
                TokenAudienceInvalid("La audiencia del token no es válida"),
                exc,
            )
        reason = (
            "signature_invalid"
            if isinstance(exc, jwt.InvalidSignatureError)
            else "claims_invalid"
        )
        self._reject(reason, algorithm, kid, TokenInvalid("Token de acceso inválido"), exc)

    @staticmethod
    def _kid_fingerprint(kid: object) -> str:
        if not isinstance(kid, str) or not kid:
            return "missing"
        return hashlib.sha256(kid.encode()).hexdigest()[:12]

    @staticmethod
    def _algorithm_label(algorithm: str) -> str:
        return algorithm if algorithm in {"HS256", "RS256", "ES256"} else "unsupported"

    def _success(self, method: str, algorithm: str, kid: object) -> None:
        logger.debug(
            "JWT verificado: method=%s algorithm=%s kid_fingerprint=%s",
            method,
            self._algorithm_label(algorithm),
            self._kid_fingerprint(kid),
        )

    def _reject(
        self,
        reason: str,
        algorithm: str,
        kid: object,
        error: DomainError,
        cause: Exception | None = None,
    ) -> NoReturn:
        logger.warning(
            "JWT rechazado: reason=%s algorithm=%s kid_fingerprint=%s",
            reason,
            self._algorithm_label(algorithm),
            self._kid_fingerprint(kid),
        )
        if cause is not None:
            raise error from cause
        raise error


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
