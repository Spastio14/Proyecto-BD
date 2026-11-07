from uuid import UUID, uuid4

import httpx
import pytest

from app.core.exceptions import (
    Conflict,
    IdentityVerificationUnavailable,
    TokenExpired,
    TokenInvalid,
)
from app.integrations.supabase import (
    AuthEmailNotConfirmed,
    AuthEmailRejected,
    AuthIdentityAlreadyExists,
    AuthPasswordRejected,
    AuthRateLimited,
    AuthSignupDisabled,
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
    with pytest.raises(AuthIdentityAlreadyExists, match="inicia sesión"):
        client().sign_up(email="cliente@example.test", password="password")


@pytest.mark.parametrize(
    ("status_code", "code", "expected"),
    [
        (422, "weak_password", AuthPasswordRejected),
        (403, "signup_disabled", AuthSignupDisabled),
        (422, "email_address_not_authorized", AuthEmailRejected),
        (429, "over_email_send_rate_limit", AuthRateLimited),
        (429, "over_request_rate_limit", AuthRateLimited),
        (403, "email_not_confirmed", AuthEmailNotConfirmed),
    ],
)
def test_auth_official_error_codes_have_specific_safe_diagnostics(
    monkeypatch, status_code, code, expected
):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: response(status_code, {"error_code": code}),
    )
    with pytest.raises(expected):
        client().sign_up(email="cliente@example.test", password="password")


def test_signup_network_error_is_service_unavailable(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("unavailable", request=httpx.Request("POST", "https://x"))

    monkeypatch.setattr(httpx, "post", fail)
    with pytest.raises(ExternalServiceUnavailable, match="temporalmente"):
        client().sign_up(email="cliente@example.test", password="password")


def test_signup_unexpected_error_payload_remains_safe(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: response(400, ["respuesta", "no", "compatible"]),
    )
    with pytest.raises(Conflict, match="revisa los datos"):
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


def test_employee_invitation_accepts_root_user_and_uses_server_headers(monkeypatch):
    expected = uuid4()
    captured = {}

    def fake_post(*args, **kwargs):
        captured["url"] = args[0]
        captured.update(kwargs)
        return response(200, auth_user(user_id=expected, email="empleado@example.test"))

    monkeypatch.setattr(httpx, "post", fake_post)
    result = client().invite_user(
        email="empleado@example.test",
        redirect_to="http://127.0.0.1:8000/app/activar-empleado/",
    )
    assert result == str(expected)
    assert captured["headers"] == {"apikey": "sb_secret_example"}
    assert "redirect_to=" in captured["url"]


def auth_session():
    return {
        "access_token": "header.payload.signature",
        "refresh_token": "refresh-token",
        "expires_in": 3600,
        "token_type": "bearer",
    }


def test_invitation_token_hash_is_verified_with_public_key(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured["url"] = args[0]
        captured.update(kwargs)
        return response(200, auth_session())

    monkeypatch.setattr(httpx, "post", fake_post)
    session = client().exchange_invitation(token_hash="secure-invitation-token-hash")
    assert session["access_token"] == "header.payload.signature"
    assert captured["url"].endswith("/auth/v1/verify")
    assert captured["headers"] == {"apikey": "sb_publishable_example"}
    assert captured["json"] == {
        "token_hash": "secure-invitation-token-hash",
        "type": "invite",
    }


def test_recovery_token_hash_uses_official_verification_type(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured["url"] = args[0]
        captured.update(kwargs)
        return response(200, auth_session())

    monkeypatch.setattr(httpx, "post", fake_post)
    client().exchange_invitation(
        token_hash="secure-recovery-token-hash",
        verification_type="recovery",
    )
    assert captured["json"] == {
        "token_hash": "secure-recovery-token-hash",
        "type": "recovery",
    }
    assert captured["headers"] == {"apikey": "sb_publishable_example"}


def test_employee_recovery_uses_public_key_and_exact_redirect(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured["url"] = args[0]
        captured.update(kwargs)
        return response(200, {})

    monkeypatch.setattr(httpx, "post", fake_post)
    client().send_password_recovery(
        email="empleado@example.test",
        redirect_to="http://127.0.0.1:8000/app/activar-empleado/",
    )
    assert captured["headers"] == {"apikey": "sb_publishable_example"}
    assert captured["json"] == {"email": "empleado@example.test"}
    assert "redirect_to=http://127.0.0.1:8000/app/activar-empleado/" in captured["url"]
    assert "sb_secret_example" not in captured["headers"].values()


def test_pkce_invitation_code_uses_official_token_exchange(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured["url"] = args[0]
        captured.update(kwargs)
        return response(200, auth_session())

    monkeypatch.setattr(httpx, "post", fake_post)
    client().exchange_code(code="auth-code", code_verifier="v" * 48)
    assert captured["url"].endswith("/auth/v1/token?grant_type=pkce")
    assert captured["json"] == {"auth_code": "auth-code", "code_verifier": "v" * 48}


def test_initial_password_uses_user_jwt_and_never_server_secret(monkeypatch):
    captured = {}

    def fake_put(*args, **kwargs):
        captured.update(kwargs)
        return response(200, auth_user())

    monkeypatch.setattr(httpx, "put", fake_put)
    client().update_password(access_token="employee-access-token", password="new-password")
    assert captured["headers"] == {
        "apikey": "sb_publishable_example",
        "Authorization": "Bearer employee-access-token",
    }
    assert captured["json"] == {"password": "new-password"}


def test_email_change_uses_user_jwt_and_public_key(monkeypatch):
    captured = {}

    def fake_put(*args, **kwargs):
        captured["url"] = args[0]
        captured.update(kwargs)
        return response(200, auth_user(email="nuevo@example.test"))

    monkeypatch.setattr(httpx, "put", fake_put)
    client().request_email_change(
        access_token="verified-user-token",
        new_email="NUEVO@example.test",
    )
    assert captured["url"].endswith("/auth/v1/user")
    assert captured["headers"] == {
        "apikey": "sb_publishable_example",
        "Authorization": "Bearer verified-user-token",
    }
    assert captured["json"] == {"email": "nuevo@example.test"}
    assert "sb_secret_example" not in captured["headers"].values()


@pytest.mark.parametrize("payload", [{}, {"access_token": "only"}, [], "invalid"])
def test_invitation_rejects_invalid_session_payload(monkeypatch, payload):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response(200, payload))
    with pytest.raises(ExternalServiceUnavailable, match="sesión válida|respuesta inválida"):
        client().exchange_invitation(token_hash="secure-invitation-token-hash")


def test_hs256_validation_uses_official_user_endpoint_and_public_headers(monkeypatch):
    expected = uuid4()
    captured = {}

    def fake_get(*args, **kwargs):
        captured["url"] = args[0]
        captured.update(kwargs)
        return response(200, {"id": str(expected), "email": "USER@EXAMPLE.TEST"})

    monkeypatch.setattr(httpx, "get", fake_get)
    identity = client().validate_access_token(access_token="user-access-token")
    assert identity == {"id": str(expected), "email": "user@example.test"}
    assert captured["url"].endswith("/auth/v1/user")
    assert captured["headers"] == {
        "apikey": "sb_publishable_example",
        "Authorization": "Bearer user-access-token",
    }
    assert "sb_secret_example" not in captured["headers"].values()


@pytest.mark.parametrize(
    ("status_code", "error_code", "expected"),
    [
        (401, "bad_jwt", TokenInvalid),
        (401, "token_expired", TokenExpired),
        (401, "invalid_api_key", IdentityVerificationUnavailable),
        (429, "over_request_rate_limit", IdentityVerificationUnavailable),
        (503, "service_unavailable", IdentityVerificationUnavailable),
    ],
)
def test_hs256_validation_distinguishes_remote_failures(
    monkeypatch, status_code, error_code, expected
):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: response(status_code, {"error_code": error_code}),
    )
    with pytest.raises(expected):
        client().validate_access_token(access_token="user-access-token")


def test_hs256_validation_connection_failure_is_transient(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("unavailable", request=httpx.Request("GET", "https://x"))

    monkeypatch.setattr(httpx, "get", fail)
    with pytest.raises(IdentityVerificationUnavailable):
        client().validate_access_token(access_token="user-access-token")


def test_hs256_diagnostic_never_logs_access_token(monkeypatch, caplog):
    secret_token = "header-sensitive.payload-sensitive.signature-sensitive"
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: response(401, {"error_code": "bad_jwt"}),
    )
    with pytest.raises(TokenInvalid):
        client().validate_access_token(access_token=secret_token)
    assert secret_token not in caplog.text
