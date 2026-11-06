const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const {
  ApiError,
  classifyIdentityError,
  invitationInput,
  requestJSON,
  verifyIdentity,
} = require("../auth-session.js");

function response(status, payload) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

test("reintenta un fallo JWKS transitorio y acepta el segundo /auth/me", async () => {
  let calls = 0;
  const request = async () => {
    calls += 1;
    if (calls === 1) throw new ApiError("JWKS no disponible", { status: 503, code: "identity_verification_unavailable" });
    return { dashboard_inicial: "/app/cliente/" };
  };
  const identity = await verifyIdentity(request, { retries: 2 });
  assert.equal(calls, 2);
  assert.equal(identity.dashboard_inicial, "/app/cliente/");
});

test("no reintenta una sesión expirada y ordena eliminarla", async () => {
  let calls = 0;
  await assert.rejects(
    verifyIdentity(async () => {
      calls += 1;
      throw new ApiError("Sesión vencida", { status: 401, code: "token_expired" });
    }),
    /Sesión vencida/,
  );
  assert.equal(calls, 1);
  assert.equal(classifyIdentityError(new ApiError("Sesión vencida", { status: 401 })).clearSession, true);
});

test("sólo ofrece recuperación cuando falta el vínculo comercial", () => {
  const missing = classifyIdentityError(new ApiError("Falta vínculo", { status: 404, code: "account_link_missing" }));
  const forbidden = classifyIdentityError(new ApiError("Inactiva", { status: 403, code: "account_inactive" }));
  const conflict = classifyIdentityError(new ApiError("Conflicto", { status: 409, code: "conflict" }));
  assert.equal(missing.recovery, true);
  assert.equal(forbidden.recovery, false);
  assert.equal(conflict.recovery, false);
});

test("conserva estado y código de errores HTTP", async () => {
  await assert.rejects(
    requestJSON(async () => response(429, { error: "auth_rate_limited", detail: "Límite" }), "/api/v1/auth/me"),
    (error) => error.status === 429 && error.code === "auth_rate_limited",
  );
});

test("el login público nunca intenta activar empleados", () => {
  const source = fs.readFileSync(path.join(__dirname, "..", "app.js"), "utf8");
  assert.equal(source.includes("/auth/activar-empleado"), false);
});

test("distingue visita directa, invitación vencida y sesión implícita", () => {
  assert.throws(() => invitationInput("", ""), /requiere un enlace/);
  assert.throws(() => invitationInput("?error_code=otp_expired", ""), /venció/);
  assert.deepEqual(invitationInput("", "#access_token=signed&type=invite"), {
    kind: "session",
    accessToken: "signed",
  });
});

test("acepta token_hash de invitación y exige verificador para PKCE", () => {
  assert.deepEqual(invitationInput("?token_hash=secret&type=invite", ""), {
    kind: "token_hash",
    tokenHash: "secret",
  });
  assert.throws(() => invitationInput("?code=auth-code", ""), /PKCE/);
  assert.deepEqual(invitationInput("?code=auth-code", "", "verifier"), {
    kind: "pkce",
    code: "auth-code",
    codeVerifier: "verifier",
  });
});
