from uuid import UUID, uuid4

import httpx
import pytest

from app.core.exceptions import Conflict
from app.integrations.supabase import (
    AuthIdentityAlreadyExists,
    ExternalServiceUnavailable,
    SupabaseHTTPClient,
)


def auth_user(*, user_id=None, email="cliente@example.test", identities=None, **extra):
    return {
        "id": str(user_id or uuid4()),
        "email": email,
        "identities": identities
        if identities is not None
        else [{"id": str(uuid4()), "provider": "email"}],
        **extra,
    }


def response(status_code: int, payload: object) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("POST", "https://project.supabase.co/auth/v1/signup"),
    )


def client() -> SupabaseHTTPClient:
    return SupabaseHTTPClient(
        "https://project.supabase.co",
        "sb_publishable_example",
        "sb_secret_example",
    )


def test_signup_accepts_root_user_response(monkeypatch):
    expected = uuid4()
    monkeypatch.setattr(
        httpx, "post", lambda *args, **kwargs: response(200, auth_user(user_id=expected))
    )
    assert client().sign_up(email="cliente@example.test", password="password") == str(expected)


def test_signup_accepts_wrapped_user_response(monkeypatch):
    expected = uuid4()
    payload = {"user": auth_user(user_id=expected), "session": None}
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response(200, payload))
    assert client().sign_up(email="cliente@example.test", password="password") == str(expected)


def test_signup_accepts_new_user_pending_email_confirmation(monkeypatch):
    expected = uuid4()
    payload = auth_user(
        user_id=expected,
        confirmed_at=None,
        email_confirmed_at=None,
        confirmation_sent_at="2026-11-05T18:00:00Z",
    )
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response(200, payload))
    assert client().sign_up(email="cliente@example.test", password="password") == str(expected)


def test_signup_rejects_obfuscated_existing_user(monkeypatch):
    payload = auth_user(identities=[])
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response(200, payload))
    with pytest.raises(AuthIdentityAlreadyExists, match="inicia sesión"):
        client().sign_up(email="cliente@example.test", password="password")


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"id": str(uuid4()), "email": "cliente@example.test"},
        {"id": "no-es-uuid", "email": "cliente@example.test", "identities": [{}]},
        {"user": "no-es-objeto"},
        auth_user(email="otra@example.test"),
    ],
)
def test_signup_rejects_invalid_or_ambiguous_response(monkeypatch, payload):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response(200, payload))
    with pytest.raises(ExternalServiceUnavailable):
        client().sign_up(email="cliente@example.test", password="password")


def test_signup_maps_supabase_existing_user_error_to_conflict(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: response(422, {"code": "user_already_exists"}),
    )
    with pytest.raises(Conflict, match="rechazó"):
        client().sign_up(email="cliente@example.test", password="password")


def test_signup_maps_supabase_server_error_to_unavailable(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: response(500, {"message": "internal"}),
    )
    with pytest.raises(ExternalServiceUnavailable, match="no pudo completar"):
        client().sign_up(email="cliente@example.test", password="password")


def test_modern_publishable_key_uses_apikey_without_bearer(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs["headers"])
        return response(200, auth_user())

    monkeypatch.setattr(httpx, "post", fake_post)
    client().sign_up(email="cliente@example.test", password="password")
    assert captured == {"apikey": "sb_publishable_example"}


def test_modern_secret_key_is_not_used_as_bearer():
    assert client()._server_headers() == {"apikey": "sb_secret_example"}


def test_legacy_service_role_jwt_keeps_required_bearer_header():
    legacy = "eyJheader.payload.signature"
    headers = SupabaseHTTPClient(
        "https://project.supabase.co", "legacy-anon", legacy
    )._server_headers()
    assert headers == {"apikey": legacy, "Authorization": f"Bearer {legacy}"}


def test_signup_returns_canonical_uuid(monkeypatch):
    expected = uuid4()
    monkeypatch.setattr(
        httpx, "post", lambda *args, **kwargs: response(200, auth_user(user_id=expected))
    )
    result = client().sign_up(email="cliente@example.test", password="password")
    assert UUID(result) == expected
