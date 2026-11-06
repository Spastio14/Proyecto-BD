const params = new URLSearchParams(location.hash.slice(1));
const accessToken = params.get("access_token");
const state = document.querySelector("#activation-state");
const next = document.querySelector("#continue");
async function activate() {
  if (!accessToken) throw new Error("El enlace no contiene una sesión válida. Solicita una nueva invitación.");
  sessionStorage.setItem("s2r_access_token", accessToken);
  const response = await fetch("/api/v1/auth/activar-empleado", { method:"POST", headers:{ Authorization:`Bearer ${accessToken}` } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "No fue posible activar el acceso");
  const meResponse = await fetch("/api/v1/auth/me", { headers:{ Authorization:`Bearer ${accessToken}` } });
  const me = await meResponse.json().catch(() => ({}));
  if (!meResponse.ok) throw new Error(me.detail || "La cuenta se activó, pero el perfil no está disponible");
  history.replaceState(null, "", location.pathname);
  state.textContent = "Acceso activado correctamente. Abriendo tu panel…";
  next.href = me.dashboard_inicial;
  next.classList.remove("hidden");
  setTimeout(() => location.assign(me.dashboard_inicial), 900);
}
activate().catch((error) => { state.textContent = error.message; next.classList.remove("hidden"); });
