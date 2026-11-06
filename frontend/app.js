const $ = (selector) => document.querySelector(selector);
const tokenKey = "s2r_access_token";

function token() { return sessionStorage.getItem(tokenKey) || ""; }
function saveToken(value) { value ? sessionStorage.setItem(tokenKey, value) : sessionStorage.removeItem(tokenKey); }
function message(text, error = false) {
  const notice = $("#notice");
  notice.textContent = text;
  notice.className = error ? "error" : "";
  setTimeout(() => { if (notice.textContent === text) notice.textContent = ""; }, 7000);
}
async function api(path, options = {}) {
  const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) };
  if (token()) headers.Authorization = `Bearer ${token()}`;
  let response;
  try { response = await fetch(`/api/v1${path}`, { ...options, headers }); }
  catch { throw new Error("No fue posible comunicarse con la API"); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "La operación no pudo completarse");
  return data;
}
const values = (form) => Object.fromEntries(new FormData(form).entries());
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));

async function catalog() {
  const rows = await api("/catalogo");
  $("#catalog").innerHTML = rows.map((item) => `<article class="product-card"><span>${escapeHtml(item.categoria)}</span><h3>${escapeHtml(item.producto)}</h3><p>${escapeHtml(item.codigo)}</p><strong>C$ ${escapeHtml(item.precio_detalle)}</strong></article>`).join("");
}

async function identifyAndRedirect() {
  try {
    const me = await api("/auth/me");
    location.assign(me.dashboard_inicial);
    return;
  } catch (firstError) {
    try {
      await api("/auth/activar-empleado", { method: "POST" });
      const me = await api("/auth/me");
      location.assign(me.dashboard_inicial);
      return;
    } catch {
      $("#recovery").classList.remove("hidden");
      message(`${firstError.message}. Si confirmaste tu correo, completa el vínculo.`, true);
    }
  }
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const result = await api("/auth/login", { method: "POST", body: JSON.stringify(values(event.target)) });
    saveToken(result.access_token);
    await identifyAndRedirect();
  } catch (error) { message(error.message, true); }
});

$("#register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/auth/registro", { method: "POST", body: JSON.stringify(values(event.target)) });
    event.target.reset();
    message("Cuenta de cliente creada. Revisa tu correo para confirmarla antes de iniciar sesión.");
  } catch (error) { message(error.message, true); }
});

$("#recover-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/auth/completar-registro", { method: "POST", body: JSON.stringify(values(event.target)) });
    await identifyAndRedirect();
  } catch (error) { message(error.message, true); }
});

$("#refresh-catalog").addEventListener("click", () => catalog().catch((error) => message(error.message, true)));
catalog().catch((error) => message(error.message, true));
if (token()) identifyAndRedirect();
