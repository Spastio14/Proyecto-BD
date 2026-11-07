const $ = (selector) => document.querySelector(selector);
const tokenKey = "s2r_access_token";
const token = () => sessionStorage.getItem(tokenKey) || "";
const saveToken = (value) => value
  ? sessionStorage.setItem(tokenKey, value)
  : sessionStorage.removeItem(tokenKey);

function message(text, error = false) {
  const notice = $("#notice");
  notice.textContent = text;
  notice.className = error ? "error" : "";
  setTimeout(() => { if (notice.textContent === text) notice.textContent = ""; }, 7000);
}

async function api(path, options = {}, accessToken = token()) {
  const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  return AuthSession.requestJSON(fetch, `/api/v1${path}`, { ...options, headers });
}

const values = (form) => Object.fromEntries(new FormData(form).entries());
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
const formatCurrency = (value) => new Intl.NumberFormat("es-NI", { style: "currency", currency: "NIO" }).format(Number(value || 0));

async function catalog() {
  const rows = await api("/catalogo", {}, "");
  if (!rows.length) {
    $("#catalog").innerHTML = '<div class="empty-state"><h3>El catálogo está en preparación</h3><p>Vuelve pronto para conocer los productos disponibles.</p></div>';
    return;
  }
  const glyphs = ["✦", "○", "◇", "⌁"];
  $("#catalog").innerHTML = rows.map((item, index) => `<article class="product-card">
    <div class="product-media tone-${(index % 4) + 1}" aria-hidden="true"><span class="product-glyph">${glyphs[index % glyphs.length]}</span></div>
    <div class="product-card-body"><span class="product-category">${escapeHtml(item.categoria)}</span><h3>${escapeHtml(item.producto)}</h3><p class="product-code">${escapeHtml(item.codigo)}</p><strong>${escapeHtml(formatCurrency(item.precio_detalle))}</strong></div>
  </article>`).join("");
}

async function identifyAndRedirect(accessToken, { persist = false } = {}) {
  $("#recovery").classList.add("hidden");
  try {
    const me = await AuthSession.verifyIdentity(
      () => api("/auth/me", {}, accessToken),
      { retries: 2, sleep: (delay) => new Promise((resolve) => setTimeout(resolve, delay)) },
    );
    if (persist) saveToken(accessToken);
    location.assign(me.dashboard_inicial);
    return me;
  } catch (error) {
    const outcome = AuthSession.classifyIdentityError(error);
    if (outcome.clearSession) saveToken("");
    if (outcome.recovery) $("#recovery").classList.remove("hidden");
    message(outcome.message, true);
    throw error;
  }
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  let result;
  try {
    result = await api(
      "/auth/login",
      { method: "POST", body: JSON.stringify(values(event.target)) },
      "",
    );
  } catch (error) { message(error.message, true); return; }
  await identifyAndRedirect(result.access_token, { persist: true }).catch(() => {});
});

$("#register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/auth/registro", { method: "POST", body: JSON.stringify(values(event.target)) }, "");
    event.target.reset();
    message("Cuenta de cliente creada. Revisa tu correo para confirmarla antes de iniciar sesión.");
  } catch (error) { message(error.message, true); }
});

$("#recover-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/auth/completar-registro", { method: "POST", body: JSON.stringify(values(event.target)) });
    await identifyAndRedirect(token());
  } catch (error) {
    if (!(error instanceof AuthSession.ApiError)) message(error.message, true);
  }
});

$("#refresh-catalog").addEventListener("click", () => catalog().catch((error) => message(error.message, true)));
catalog().catch((error) => message(error.message, true));
if (token()) identifyAndRedirect(token()).catch(() => {});
