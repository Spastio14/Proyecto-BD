from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

import httpx

from app.core.exceptions import Conflict, DomainError


class ExternalServiceUnavailable(DomainError):
    status_code = 503
    code = "external_service_unavailable"


class AuthGateway(Protocol):
    def sign_up(self, *, email: str, password: str) -> str: ...

    def sign_in(self, *, email: str, password: str) -> dict: ...

    def delete_user(self, user_id: str) -> None: ...


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

    def _headers(self, key: str) -> dict[str, str]:
        return {"apikey": key, "Authorization": f"Bearer {key}"}

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
            headers=self._headers(self.public_key),
            json={"email": email, "password": password},
            timeout=self.timeout,
        )
        self._raise(response, "el registro")
        user = response.json().get("user") or {}
        user_id = user.get("id")
        if not user_id:
            raise Conflict("Supabase no devolvió un usuario nuevo")
        return str(user_id)

    def sign_in(self, *, email: str, password: str) -> dict:
        response = httpx.post(
            f"{self.url.rstrip('/')}/auth/v1/token?grant_type=password",
            headers=self._headers(self.public_key),
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

    def delete_user(self, user_id: str) -> None:
        if not self.secret_key:
            raise ExternalServiceUnavailable("Falta la clave privada para compensar el registro")
        response = httpx.delete(
            f"{self.url.rstrip('/')}/auth/v1/admin/users/{quote(user_id, safe='')}",
            headers=self._headers(self.secret_key),
            timeout=self.timeout,
        )
        self._raise(response, "la compensación del registro")

    def upload(self, *, bucket: str, path: str, content: bytes, content_type: str) -> None:
        if not self.secret_key:
            raise ExternalServiceUnavailable("Storage no está configurado en el servidor")
        target = f"{quote(bucket, safe='')}/{quote(path, safe='/')}"
        headers = self._headers(self.secret_key) | {
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
        if not self.secret_key:
            raise ExternalServiceUnavailable("Storage no está configurado en el servidor")
        response = httpx.delete(
            f"{self.url.rstrip('/')}/storage/v1/object/{quote(bucket, safe='')}",
            headers=self._headers(self.secret_key),
            json={"prefixes": [path]},
            timeout=self.timeout,
        )
        self._raise(response, "la compensación del archivo")

    def signed_url(self, *, bucket: str, path: str, expires_in: int) -> str:
        if not self.secret_key:
            raise ExternalServiceUnavailable("Storage no está configurado en el servidor")
        target = f"{quote(bucket, safe='')}/{quote(path, safe='/')}"
        response = httpx.post(
            f"{self.url.rstrip('/')}/storage/v1/object/sign/{target}",
            headers=self._headers(self.secret_key),
            json={"expiresIn": expires_in},
            timeout=self.timeout,
        )
        self._raise(response, "la URL firmada")
        signed = response.json().get("signedURL") or response.json().get("signedUrl")
        if not signed:
            raise ExternalServiceUnavailable("Storage no devolvió una URL firmada")
        return signed if signed.startswith("http") else f"{self.url.rstrip('/')}/storage/v1{signed}"
