const state = document.querySelector("#activation-state");
const form = document.querySelector("#activation-form");
const next = document.querySelector("#continue");
const tokenKey = "s2r_access_token";
let invitationToken = "";

function activationError(error) {
  if (!(error instanceof AuthSession.ApiError)) return error.message;
  if (error.status === 401) return "La invitación venció o ya no es válida. Solicita una nueva al administrador.";
  if (error.status === 403) return "Esta identidad no tiene autorización para activar un empleado.";
  if (error.status === 409) return error.message;
  if (error.status === 429) return "Se alcanzó el límite de solicitudes. Espera unos minutos antes de reintentar.";
  if (error.status === 503 || error.status === 0) return "La identidad no pudo verificarse temporalmente. Inténtalo de nuevo.";
  return error.message;
}

async function api(path, options = {}, accessToken = "") {
  const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  return AuthSession.requestJSON(fetch, `/api/v1${path}`, { ...options, headers });
}

async function obtainSession(input) {
  if (input.kind === "session") return input.accessToken;
  if (input.kind === "token_hash") {
    const session = await api("/auth/intercambiar-invitacion", {
      method: "POST",
      body: JSON.stringify({ token_hash: input.tokenHash, type: input.linkType }),
    });
    return session.access_token;
  }
  if (input.kind === "pkce") {
    const session = await api("/auth/intercambiar-invitacion", {
      method: "POST",
      body: JSON.stringify({ code: input.code, code_verifier: input.codeVerifier, type: input.linkType }),
    });
    sessionStorage.removeItem("s2r_pkce_code_verifier");
    return session.access_token;
  }
  throw new Error("Formato de invitación incompatible.");
}

async function prepare() {
  const input = AuthSession.invitationInput(
    location.search,
    location.hash,
    sessionStorage.getItem("s2r_pkce_code_verifier") || "",
  );
  invitationToken = await obtainSession(input);
  await AuthSession.verifyIdentity(
    () => api("/auth/validar-invitacion", {}, invitationToken),
    { retries: 2, sleep: (delay) => new Promise((resolve) => setTimeout(resolve, delay)) },
  );
  history.replaceState(null, "", location.pathname);
  state.textContent = "Invitación verificada. Define una contraseña inicial para activar tu acceso.";
  form.classList.remove("hidden");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const password = new FormData(form).get("password");
  const confirmation = new FormData(form).get("password_confirmation");
  if (password !== confirmation) {
    state.textContent = "Las contraseñas no coinciden.";
    return;
  }
  const button = form.querySelector("button");
  button.disabled = true;
  try {
    await api("/auth/activar-empleado", {
      method: "POST",
      body: JSON.stringify({ password }),
    }, invitationToken);
    const me = await AuthSession.verifyIdentity(
      () => api("/auth/me", {}, invitationToken),
      { retries: 2, sleep: (delay) => new Promise((resolve) => setTimeout(resolve, delay)) },
    );
    sessionStorage.setItem(tokenKey, invitationToken);
    state.textContent = "Acceso activado correctamente. Abriendo tu panel…";
    form.classList.add("hidden");
    next.href = me.dashboard_inicial;
    next.classList.remove("hidden");
    setTimeout(() => location.assign(me.dashboard_inicial), 900);
  } catch (error) {
    state.textContent = activationError(error);
    button.disabled = false;
  }
});

prepare().catch((error) => {
  state.textContent = activationError(error);
  next.classList.remove("hidden");
});
