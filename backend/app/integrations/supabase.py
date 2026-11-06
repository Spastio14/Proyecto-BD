from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote
from uuid import UUID

import httpx

from app.core.exceptions import Conflict, DomainError


class ExternalServiceUnavailable(DomainError):
    status_code = 503
    code = "external_service_unavailable"


class AuthIdentityAlreadyExists(Conflict):
    code = "auth_identity_already_exists"


class AuthGateway(Protocol):
    def sign_up(self, *, email: str, password: str) -> str: ...

    def sign_in(self, *, email: str, password: str) -> dict: ...


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
    def _raise(response: httpx.Response, operation: str) -> None:
        if response.is_success:
            return
        if response.status_code in {400, 409, 422}:
            raise Conflict(f"Supabase rechazó {operation}")
        raise ExternalServiceUnavailable(f"Supabase no pudo completar {operation}")

    def sign_up(self, *, email: str, password: str) -> str:
        response = httpx.post(
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
        response = httpx.post(
            f"{self.url.rstrip('/')}/auth/v1/token?grant_type=password",
            headers=self._public_headers(),
            json={"email": email, "password": password},
            timeout=self.timeout,
        )
        self._raise(response, "el inicio de sesión")
        data = response.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_in": data["expires_in"],
            "token_type": data.get("token_type", "bearer"),
        }

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
