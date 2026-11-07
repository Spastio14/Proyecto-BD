import logging
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote
from uuid import UUID

import httpx

from app.core.exceptions import (
    AuthenticationRequired,
    Conflict,
    DomainError,
    IdentityVerificationUnavailable,
    TokenExpired,
    TokenInvalid,
)

logger = logging.getLogger(__name__)


class ExternalServiceUnavailable(DomainError):
    status_code = 503
    code = "external_service_unavailable"


class AuthIdentityAlreadyExists(Conflict):
    code = "auth_identity_already_exists"


class AuthPasswordRejected(DomainError):
    status_code = 422
    code = "auth_password_rejected"


class AuthSignupDisabled(DomainError):
    status_code = 403
    code = "auth_signup_disabled"


class AuthEmailRejected(DomainError):
    status_code = 422
    code = "auth_email_rejected"


class AuthEmailNotConfirmed(DomainError):
    status_code = 403
    code = "auth_email_not_confirmed"


class AuthRateLimited(DomainError):
    status_code = 429
    code = "auth_rate_limited"


@dataclass(frozen=True, slots=True)
class AuthAdminIdentity:
    subject: str
    email: str


class AuthGateway(Protocol):
    def sign_up(self, *, email: str, password: str) -> str: ...

    def sign_in(self, *, email: str, password: str) -> dict: ...

    def invite_user(self, *, email: str, redirect_to: str | None = None) -> str: ...

    def send_password_recovery(
        self, *, email: str, redirect_to: str | None = None
    ) -> None: ...

    def get_user(self, *, subject: str) -> AuthAdminIdentity: ...

    def exchange_invitation(
        self, *, token_hash: str, verification_type: str = "invite"
    ) -> dict: ...

    def exchange_code(self, *, code: str, code_verifier: str) -> dict: ...

    def update_password(self, *, access_token: str, password: str) -> None: ...

    def request_email_change(self, *, access_token: str, new_email: str) -> None: ...

    def validate_access_token(self, *, access_token: str) -> dict[str, str | None]: ...


class StorageGateway(Protocol):
    def upload(self, *, bucket: str, path: str, content: bytes, content_type: str) -> None: ...

    def delete(self, *, bucket: str, path: str) -> None: ...

    def signed_url(self, *, bucket: str, path: str, expires_in: int) -> str: ...


@dataclass(slots=True)
class SupabaseHTTPClient:
    url: str
    public_key: str
    secret_key: str | None = None
    timeout: float = 15.0

    @staticmethod
    def _is_legacy_jwt_key(key: str) -> bool:
        return key.startswith("eyJ") and key.count(".") == 2

    def _public_headers(self) -> dict[str, str]:
        # Las claves publishable modernas y anon heredadas se envían como apikey.
        return {"apikey": self.public_key}

    def _server_headers(self) -> dict[str, str]:
        if not self.secret_key:
            raise ExternalServiceUnavailable("Falta la clave privada del servidor")
        headers = {"apikey": self.secret_key}
        # Sólo las service_role heredadas son JWT válidos para Authorization.
        # sb_secret_* no es un bearer token y no debe enviarse como tal.
        if self._is_legacy_jwt_key(self.secret_key):
            headers["Authorization"] = f"Bearer {self.secret_key}"
        return headers

    @staticmethod
    def _error_code(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
        for key in ("code", "error_code"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return None

    @classmethod
    def _raise(cls, response: httpx.Response, operation: str) -> None:
        if response.is_success:
            return
        error_code = cls._error_code(response)
        logger.warning(
            "Supabase Auth rechazó una operación: operation=%s status=%s code=%s",
            operation,
            response.status_code,
            error_code or "unknown",
        )
        if response.status_code == 429 or error_code in {
            "over_email_send_rate_limit",
            "over_request_rate_limit",
        }:
            raise AuthRateLimited(
                "Hay demasiadas solicitudes de autenticación. "
                "Espera unos minutos e inténtalo de nuevo"
            )
        if error_code in {"weak_password", "password_too_short"}:
            raise AuthPasswordRejected(
                "La contraseña no cumple los requisitos de seguridad del servicio"
            )
        if error_code in {"signup_disabled", "email_provider_disabled"}:
            raise AuthSignupDisabled(
                "El registro de nuevas cuentas está deshabilitado temporalmente"
            )
        if error_code == "email_not_confirmed":
            raise AuthEmailNotConfirmed("Confirma tu correo electrónico antes de iniciar sesión")
        if error_code in {"email_address_not_authorized", "email_address_invalid"}:
            raise AuthEmailRejected(
                "El servicio de correo no puede autorizar esa dirección en este momento"
            )
        if error_code in {"invalid_credentials", "invalid_grant"}:
            raise AuthenticationRequired("Correo o contraseña incorrectos")
        if error_code in {"email_exists", "user_already_exists"}:
            raise AuthIdentityAlreadyExists(
                "No fue posible crear la cuenta. Si ya te registraste, "
                "inicia sesión o completa el vínculo"
            )
        if response.status_code in {400, 409, 422}:
            raise Conflict(f"Supabase rechazó {operation}; revisa los datos e inténtalo nuevamente")
        raise ExternalServiceUnavailable(f"Supabase no pudo completar {operation}")

    @staticmethod
    def _post(*args, **kwargs) -> httpx.Response:
        try:
            return httpx.post(*args, **kwargs)
        except httpx.RequestError as exc:
            logger.warning("Fallo de red al comunicarse con Supabase Auth: %s", type(exc).__name__)
            raise ExternalServiceUnavailable(
                "El servicio de autenticación no está disponible temporalmente"
            ) from exc

    @staticmethod
    def _get(*args, **kwargs) -> httpx.Response:
        try:
            return httpx.get(*args, **kwargs)
        except httpx.RequestError as exc:
            logger.warning("Fallo de red al consultar Supabase Auth: %s", type(exc).__name__)
            raise ExternalServiceUnavailable(
                "El servicio de autenticación no está disponible temporalmente"
            ) from exc

    @staticmethod
    def _put(*args, **kwargs) -> httpx.Response:
        try:
            return httpx.put(*args, **kwargs)
        except httpx.RequestError as exc:
            logger.warning("Fallo de red al comunicarse con Supabase Auth: %s", type(exc).__name__)
            raise ExternalServiceUnavailable(
                "El servicio de autenticación no está disponible temporalmente"
            ) from exc

    @staticmethod
    def _session(payload: object, operation: str) -> dict:
        if not isinstance(payload, dict):
            raise ExternalServiceUnavailable(
                f"Supabase devolvió una respuesta inválida durante {operation}"
            )
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        if (
            not isinstance(access_token, str)
            or not access_token
            or not isinstance(refresh_token, str)
            or not refresh_token
            or not isinstance(expires_in, (int, float))
        ):
            raise ExternalServiceUnavailable(
                f"Supabase no devolvió una sesión válida durante {operation}"
            )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "token_type": payload.get("token_type", "bearer"),
        }

    def sign_up(self, *, email: str, password: str) -> str:
        response = self._post(
            f"{self.url.rstrip('/')}/auth/v1/signup",
            headers=self._public_headers(),
            json={"email": email, "password": password},
            timeout=self.timeout,
        )
        self._raise(response, "el registro")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceUnavailable(
                "Supabase devolvió una respuesta de registro inválida"
            ) from exc
        return self._new_signup_user_id(payload, requested_email=email)

    @staticmethod
    def _new_signup_user_id(payload: object, *, requested_email: str) -> str:
        if not isinstance(payload, dict):
            raise ExternalServiceUnavailable("Supabase devolvió una respuesta de registro inválida")
        candidate = payload.get("user", payload)
        if not isinstance(candidate, dict):
            raise ExternalServiceUnavailable("Supabase devolvió una respuesta de registro inválida")

        identities = candidate.get("identities")
        if not isinstance(identities, list):
            raise ExternalServiceUnavailable(
                "Supabase no informó las identidades del usuario registrado"
            )
        # GoTrue devuelve un usuario saneado con UUID ficticio e identities=[]
        # para no revelar si un correo confirmado ya estaba registrado.
        if not identities:
            raise AuthIdentityAlreadyExists(
                "El correo ya está registrado; inicia sesión para recuperar el vínculo"
            )
        if any(not isinstance(identity, dict) for identity in identities):
            raise ExternalServiceUnavailable("Supabase devolvió identidades de registro inválidas")

        returned_email = candidate.get("email")
        if not isinstance(returned_email, str) or (
            returned_email.strip().lower() != requested_email.strip().lower()
        ):
            raise ExternalServiceUnavailable(
                "Supabase devolvió una identidad distinta de la solicitada"
            )
        try:
            return str(UUID(str(candidate.get("id", ""))))
        except ValueError as exc:
            raise ExternalServiceUnavailable(
                "Supabase devolvió un identificador de usuario inválido"
            ) from exc

    def sign_in(self, *, email: str, password: str) -> dict:
        response = self._post(
            f"{self.url.rstrip('/')}/auth/v1/token?grant_type=password",
            headers=self._public_headers(),
            json={"email": email, "password": password},
            timeout=self.timeout,
        )
        self._raise(response, "el inicio de sesión")
        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceUnavailable(
                "Supabase devolvió una respuesta de inicio de sesión inválida"
            ) from exc
        return self._session(data, "el inicio de sesión")

    def validate_access_token(self, *, access_token: str) -> dict[str, str | None]:
        """Delega en Supabase Auth la firma de tokens HS256 heredados."""
        try:
            response = self._get(
                f"{self.url.rstrip('/')}/auth/v1/user",
                headers=self._public_headers()
                | {"Authorization": f"Bearer {access_token}"},
                timeout=self.timeout,
            )
        except ExternalServiceUnavailable as exc:
            raise IdentityVerificationUnavailable(
                "No fue posible verificar la sesión con Supabase Auth"
            ) from exc
        if not response.is_success:
            error_code = self._error_code(response)
            logger.warning(
                "Supabase rechazó la validación del JWT: status=%s code=%s",
                response.status_code,
                error_code or "unknown",
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise IdentityVerificationUnavailable(
                    "Supabase Auth no puede verificar la sesión temporalmente"
                )
            if error_code in {"session_expired", "token_expired"}:
                raise TokenExpired("La sesión venció; inicia sesión nuevamente")
            if error_code in {"invalid_api_key", "api_key_invalid"}:
                raise IdentityVerificationUnavailable(
                    "La clave publicable de Supabase no es válida"
                )
            raise TokenInvalid("Supabase rechazó el token de acceso")
        try:
            payload = response.json()
        except ValueError as exc:
            raise IdentityVerificationUnavailable(
                "Supabase devolvió una identidad incompatible"
            ) from exc
        if not isinstance(payload, dict):
            raise IdentityVerificationUnavailable(
                "Supabase devolvió una identidad incompatible"
            )
        try:
            subject = str(UUID(str(payload.get("id", ""))))
        except ValueError as exc:
            raise IdentityVerificationUnavailable(
                "Supabase devolvió una identidad sin UUID válido"
            ) from exc
        email = payload.get("email")
        if email is not None and not isinstance(email, str):
            raise IdentityVerificationUnavailable(
                "Supabase devolvió una identidad incompatible"
            )
        return {
            "id": subject,
            "email": email.strip().lower() if isinstance(email, str) else None,
        }

    def exchange_invitation(
        self, *, token_hash: str, verification_type: str = "invite"
    ) -> dict:
        if verification_type not in {"invite", "recovery"}:
            raise TokenInvalid("El tipo de enlace Auth no está permitido")
        response = self._post(
            f"{self.url.rstrip('/')}/auth/v1/verify",
            headers=self._public_headers(),
            json={"token_hash": token_hash, "type": verification_type},
            timeout=self.timeout,
        )
        self._raise(response, "la verificación de la invitación")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceUnavailable(
                "Supabase devolvió una verificación de invitación inválida"
            ) from exc
        return self._session(payload, "la verificación de la invitación")

    def exchange_code(self, *, code: str, code_verifier: str) -> dict:
        response = self._post(
            f"{self.url.rstrip('/')}/auth/v1/token?grant_type=pkce",
            headers=self._public_headers(),
            json={"auth_code": code, "code_verifier": code_verifier},
            timeout=self.timeout,
        )
        self._raise(response, "el intercambio PKCE de la invitación")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceUnavailable(
                "Supabase devolvió un intercambio PKCE inválido"
            ) from exc
        return self._session(payload, "el intercambio PKCE de la invitación")

    def update_password(self, *, access_token: str, password: str) -> None:
        headers = self._public_headers() | {"Authorization": f"Bearer {access_token}"}
        response = self._put(
            f"{self.url.rstrip('/')}/auth/v1/user",
            headers=headers,
            json={"password": password},
            timeout=self.timeout,
        )
        self._raise(response, "la definición de la contraseña inicial")

    def request_email_change(self, *, access_token: str, new_email: str) -> None:
        headers = self._public_headers() | {"Authorization": f"Bearer {access_token}"}
        response = self._put(
            f"{self.url.rstrip('/')}/auth/v1/user",
            headers=headers,
            json={"email": new_email.strip().lower()},
            timeout=self.timeout,
        )
        self._raise(response, "la solicitud de cambio de correo")

    def invite_user(self, *, email: str, redirect_to: str | None = None) -> str:
        endpoint = f"{self.url.rstrip('/')}/auth/v1/invite"
        if redirect_to:
            endpoint = f"{endpoint}?redirect_to={quote(redirect_to, safe=':/')}"
        response = self._post(
            endpoint,
            headers=self._server_headers(),
            json={"email": email},
            timeout=self.timeout,
        )
        self._raise(response, "la invitación del empleado")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceUnavailable("Supabase devolvió una invitación inválida") from exc
        return self._admin_user(payload, requested_email=email).subject

    def send_password_recovery(
        self, *, email: str, redirect_to: str | None = None
    ) -> None:
        endpoint = f"{self.url.rstrip('/')}/auth/v1/recover"
        if redirect_to:
            endpoint = f"{endpoint}?redirect_to={quote(redirect_to, safe=':/')}"
        response = self._post(
            endpoint,
            headers=self._public_headers(),
            json={"email": email},
            timeout=self.timeout,
        )
        self._raise(response, "la recuperación de acceso del empleado")

    def get_user(self, *, subject: str) -> AuthAdminIdentity:
        try:
            canonical = str(UUID(subject))
        except ValueError as exc:
            raise Conflict("El identificador Auth no es un UUID válido") from exc
        response = self._get(
            f"{self.url.rstrip('/')}/auth/v1/admin/users/{canonical}",
            headers=self._server_headers(),
            timeout=self.timeout,
        )
        self._raise(response, "la verificación administrativa de la identidad")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceUnavailable(
                "Supabase devolvió una identidad administrativa inválida"
            ) from exc
        return self._admin_user(payload)

    @staticmethod
    def _admin_user(payload: object, *, requested_email: str | None = None) -> AuthAdminIdentity:
        if not isinstance(payload, dict):
            raise ExternalServiceUnavailable("Supabase devolvió una identidad inválida")
        candidate = payload.get("user", payload)
        if not isinstance(candidate, dict):
            raise ExternalServiceUnavailable("Supabase devolvió una identidad inválida")
        email = candidate.get("email")
        if not isinstance(email, str) or "@" not in email:
            raise ExternalServiceUnavailable("Supabase no informó un correo verificable")
        normalized = email.strip().lower()
        if requested_email and normalized != requested_email.strip().lower():
            raise ExternalServiceUnavailable("Supabase devolvió una identidad distinta")
        try:
            subject = str(UUID(str(candidate.get("id", ""))))
        except ValueError as exc:
            raise ExternalServiceUnavailable("Supabase devolvió un UUID inválido") from exc
        return AuthAdminIdentity(subject=subject, email=normalized)

    def upload(self, *, bucket: str, path: str, content: bytes, content_type: str) -> None:
        target = f"{quote(bucket, safe='')}/{quote(path, safe='/')}"
        headers = self._server_headers() | {
            "content-type": content_type,
            "x-upsert": "false",
        }
        response = httpx.post(
            f"{self.url.rstrip('/')}/storage/v1/object/{target}",
            headers=headers,
            content=content,
            timeout=self.timeout,
        )
        self._raise(response, "la carga del archivo")

    def delete(self, *, bucket: str, path: str) -> None:
        response = httpx.delete(
            f"{self.url.rstrip('/')}/storage/v1/object/{quote(bucket, safe='')}",
            headers=self._server_headers(),
            json={"prefixes": [path]},
            timeout=self.timeout,
        )
        self._raise(response, "la compensación del archivo")

    def signed_url(self, *, bucket: str, path: str, expires_in: int) -> str:
        target = f"{quote(bucket, safe='')}/{quote(path, safe='/')}"
        response = httpx.post(
            f"{self.url.rstrip('/')}/storage/v1/object/sign/{target}",
            headers=self._server_headers(),
            json={"expiresIn": expires_in},
            timeout=self.timeout,
        )
        self._raise(response, "la URL firmada")
        signed = response.json().get("signedURL") or response.json().get("signedUrl")
        if not signed:
            raise ExternalServiceUnavailable("Storage no devolvió una URL firmada")
        return signed if signed.startswith("http") else f"{self.url.rstrip('/')}/storage/v1{signed}"
