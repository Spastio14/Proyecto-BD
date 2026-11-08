(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.AuthSession = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  class ApiError extends Error {
    constructor(message, { status = 0, code = "network_error" } = {}) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.code = code;
    }
  }

  function validationMessage(detail) {
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail.map((item) => {
        if (typeof item === "string") return item;
        if (!item || typeof item !== "object") return "Dato inválido";
        const location = Array.isArray(item.loc)
          ? item.loc.filter((part) => !["body", "query", "path"].includes(part)).join(" → ")
          : "";
        const message = typeof item.msg === "string" ? item.msg : "Dato inválido";
        return location ? `${location}: ${message}` : message;
      }).filter(Boolean);
      if (messages.length) return messages.join(". ");
    }
    if (detail && typeof detail === "object") {
      if (typeof detail.message === "string") return detail.message;
      if (typeof detail.msg === "string") return detail.msg;
    }
    return "La operación no pudo completarse";
  }

  async function requestJSON(fetchImpl, url, options = {}) {
    let response;
    try { response = await fetchImpl(url, options); }
    catch { throw new ApiError("No fue posible comunicarse con la API"); }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new ApiError(validationMessage(data.detail), {
        status: response.status,
        code: typeof data.error === "string" ? data.error : "http_error",
      });
    }
    return data;
  }

  const isTransient = (error) =>
    error instanceof ApiError && [0, 429, 503].includes(error.status);

  async function verifyIdentity(request, { retries = 2, sleep = () => Promise.resolve() } = {}) {
    let attempt = 0;
    while (true) {
      try { return await request(); }
      catch (error) {
        if (!isTransient(error) || attempt >= retries) throw error;
        attempt += 1;
        await sleep(250 * attempt);
      }
    }
  }

  function classifyIdentityError(error) {
    if (!(error instanceof ApiError)) {
      return { message: "No fue posible verificar la sesión", clearSession: false, recovery: false };
    }
    if (error.status === 401) return { message: error.message, clearSession: true, recovery: false };
    if (error.status === 403) {
      return {
        message: error.code === "account_inactive"
          ? "La cuenta o el perfil están inactivos. Si eres empleado, usa el enlace privado de invitación."
          : error.message,
        clearSession: false,
        recovery: false,
      };
    }
    if (error.status === 404 && error.code === "account_link_missing") {
      return { message: error.message, clearSession: false, recovery: true };
    }
    if (error.status === 409) return { message: error.message, clearSession: false, recovery: false };
    if (error.status === 429) return { message: "Hay demasiadas solicitudes. Espera un momento e inténtalo de nuevo.", clearSession: false, recovery: false };
    if (error.status === 503 || error.status === 0) return { message: "No fue posible verificar la identidad temporalmente. Inténtalo de nuevo.", clearSession: false, recovery: false };
    return { message: error.message, clearSession: false, recovery: false };
  }

  function invitationInput(search, fragment, codeVerifier = "") {
    const query = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
    const hash = new URLSearchParams(fragment.startsWith("#") ? fragment.slice(1) : fragment);
    const errorCode = query.get("error_code") || hash.get("error_code") || query.get("error") || hash.get("error");
    if (errorCode) {
      if (["otp_expired", "access_denied"].includes(errorCode)) {
        throw new Error("La invitación venció o ya fue utilizada. Solicita una nueva al administrador.");
      }
      throw new Error(query.get("error_description") || hash.get("error_description") || "Supabase rechazó el enlace de invitación.");
    }
    const accessToken = hash.get("access_token");
    const linkType = query.get("type") || hash.get("type") || "invite";
    if (!["invite", "recovery"].includes(linkType)) {
      throw new Error("El enlace no corresponde a una activación de empleado.");
    }
    if (accessToken) return { kind: "session", accessToken, linkType };
    const tokenHash = query.get("token_hash");
    if (tokenHash) {
      return { kind: "token_hash", tokenHash, linkType };
    }
    const code = query.get("code");
    if (code) {
      if (!codeVerifier) throw new Error("El enlace PKCE no pertenece a esta sesión del navegador. Solicita una nueva invitación.");
      return { kind: "pkce", code, codeVerifier, linkType };
    }
    throw new Error("Esta página requiere un enlace de invitación enviado por un administrador.");
  }

  return { ApiError, requestJSON, validationMessage, verifyIdentity, classifyIdentityError, invitationInput, isTransient };
});
