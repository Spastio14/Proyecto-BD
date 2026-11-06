const $ = (selector) => document.querySelector(selector);
const accessToken = () => sessionStorage.getItem("s2r_access_token") || "";
const scope = document.body.dataset.scope;
const expectedDashboard = document.body.dataset.dashboard;
let identity;

function notice(text, error = false) {
  const output = $("#notice");
  output.textContent = text;
  output.className = error ? "error" : "";
  setTimeout(() => { if (output.textContent === text) output.textContent = ""; }, 6500);
}
async function api(path, options = {}) {
  const form = options.body instanceof FormData;
  const headers = { ...(form || !options.body ? {} : { "Content-Type":"application/json" }), ...(options.headers || {}), Authorization:`Bearer ${accessToken()}` };
  let response;
  try { response = await fetch(`/api/v1${path}`, { ...options, headers }); }
  catch { throw new Error("No fue posible comunicarse con la API"); }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[char]));
const display = (value) => Array.isArray(value) ? value.join(", ") : typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "");
const fields = (form) => Object.fromEntries(new FormData(form).entries());
const permitted = (code) => identity.permisos.includes(code);
function table(rows, columns) {
  if (!rows.length) return '<div class="panel"><p class="muted">No hay registros para mostrar.</p></div>';
  const keys = columns || Object.keys(rows[0]);
  return `<div class="table-wrap"><table><thead><tr>${keys.map((key) => `<th>${escapeHtml(key)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${keys.map((key) => `<td>${escapeHtml(display(row[key]))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function options(rows, value, label) { return rows.map((row) => `<option value="${row[value]}">${escapeHtml(row[label])}</option>`).join(""); }
function setContent(title, html) { $("#view-title").textContent = title; $("#content").innerHTML = html; }

const menus = {
  cliente: [["summary","Resumen"],["orders","Mis pedidos"],["quotes","Mis cotizaciones"],["payments","Pagos"],["catalog","Catálogo"],["tracking","Seguimiento"],["profile","Mi perfil"]],
  admin: [["summary","Resumen"],["orders","Pedidos","PEDIDO_GESTIONAR"],["quotes","Cotizaciones","PEDIDO_GESTIONAR"],["clients","Clientes","PEDIDO_GESTIONAR"],["catalog","Productos"],["inventory","Inventario","INVENTARIO_CONSULTAR"],["purchases","Compras","COMPRA_CONSULTAR"],["providers","Proveedores","PROVEEDOR_CONSULTAR"],["payments","Pagos","PAGO_CONSULTAR"],["losses","Pérdidas","PERDIDA_CONSULTAR"],["reports","Reportes","REPORTE_FINANCIERO_CONSULTAR"],["employees","Empleados y roles","EMPLEADO_GESTIONAR"],["profile","Mi perfil"]],
  contabilidad: [["summary","Resumen financiero","REPORTE_FINANCIERO_CONSULTAR"],["payments","Ingresos verificados","PAGO_CONSULTAR"],["purchases","Compras","COMPRA_CONSULTAR"],["inventory","Inventario","INVENTARIO_CONSULTAR"],["losses","Pérdidas","PERDIDA_CONSULTAR"],["reports","Reportes","REPORTE_FINANCIERO_CONSULTAR"],["profile","Mi perfil"]],
  ventas: [["orders","Pedidos","PEDIDO_GESTIONAR"],["quotes","Cotizaciones","PEDIDO_GESTIONAR"],["clients","Clientes","PEDIDO_GESTIONAR"],["payments","Pagos","PAGO_CONSULTAR"],["catalog","Productos"],["profile","Mi perfil"]],
  produccion: [["orders","Pedidos","PEDIDO_GESTIONAR"],["designs","Diseños","DISENO_APROBAR"],["inventory","Inventario","INVENTARIO_CONSULTAR"],["losses","Incidencias","PERDIDA_CONSULTAR"],["profile","Mi perfil"]]
};

async function summary() {
  if (scope === "cliente") {
    const [orders, quotes] = await Promise.all([api("/pedidos"), api("/cotizaciones")]);
    setContent("Mi resumen", `<div class="metrics"><article class="metric"><span>Pedidos</span><strong>${orders.length}</strong></article><article class="metric"><span>Cotizaciones</span><strong>${quotes.length}</strong></article><article class="metric"><span>Activos</span><strong>${orders.filter((x) => !["ENTREGADO","CANCELADO","EXPIRADO"].includes(x.estado)).length}</strong></article></div>${table(orders.slice(0,5))}`);
    return;
  }
  if (permitted("REPORTE_FINANCIERO_CONSULTAR")) {
    const report = await api("/reportes/resumen");
    setContent("Resumen", `<div class="metrics"><article class="metric"><span>Ingreso verificado</span><strong>C$ ${escapeHtml(report.ingresos_verificados)}</strong></article><article class="metric"><span>Artículos</span><strong>${report.inventario.length}</strong></article><article class="metric"><span>Movimientos recientes</span><strong>${report.movimientos_inventario.length}</strong></article></div><h2>Productos más vendidos</h2>${table(report.productos_mas_vendidos)}<h2>Compras por proveedor</h2>${table(report.compras_por_proveedor)}`);
  } else {
    const orders = await api("/pedidos");
    setContent("Trabajo pendiente", `<div class="metrics"><article class="metric"><span>Pedidos visibles</span><strong>${orders.length}</strong></article><article class="metric"><span>En producción</span><strong>${orders.filter((x) => x.estado === "EN_PRODUCCION").length}</strong></article></div>${table(orders)}`);
  }
}

async function orders() {
  const rows = await api("/pedidos");
  let form = "";
  if (permitted("PEDIDO_GESTIONAR") && rows.length) form = `<article class="panel result"><h2>Actualizar estado operativo</h2><form id="order-state" class="form-grid inline"><label>Pedido<select name="id">${rows.map((x) => `<option value="${x.id_pedido}">${escapeHtml(x.codigo_pedido)} · ${escapeHtml(x.estado)}</option>`).join("")}</select></label><label>Estado<select name="target"><option>EN_DISENO</option><option>LISTO</option></select></label><label>Motivo<input name="reason" required></label><button>Actualizar</button></form></article>`;
  setContent(scope === "cliente" ? "Mis pedidos" : "Pedidos", table(rows) + form);
  $("#order-state")?.addEventListener("submit", async (event) => { event.preventDefault(); const data = fields(event.target); try { await api(`/pedidos/${data.id}/estado`, { method:"POST", body:JSON.stringify({ target:data.target, reason:data.reason }) }); notice("Pedido actualizado"); await orders(); } catch (error) { notice(error.message,true); } });
}

async function quotes() {
  const rows = await api("/cotizaciones");
  const form = scope === "cliente" && rows.length ? `<article class="panel result"><h2>Decidir cotización</h2><form id="quote-decision" class="form-grid inline"><label>Cotización<select name="id">${rows.map((x) => `<option value="${x.id_cotizacion}">#${x.id_cotizacion} · ${escapeHtml(x.estado)} · C$ ${escapeHtml(x.total_ofrecido)}</option>`).join("")}</select></label><label>Acción<select name="decision"><option>ACEPTADA</option><option>RECHAZADA</option><option>CONVERTIR</option></select></label><label>Motivo<input name="reason" value="Decisión del cliente"></label><button>Aplicar</button></form></article>` : "";
  setContent(scope === "cliente" ? "Mis cotizaciones" : "Cotizaciones", table(rows) + form);
  $("#quote-decision")?.addEventListener("submit", async (event) => { event.preventDefault(); const data = fields(event.target); try { if (data.decision === "CONVERTIR") await api(`/cotizaciones/${data.id}/convertir`, { method:"POST" }); else await api(`/cotizaciones/${data.id}/decision`, { method:"POST", body:JSON.stringify({ decision:data.decision, reason:data.reason }) }); notice("Cotización actualizada"); await quotes(); } catch (error) { notice(error.message,true); } });
}

async function catalog() {
  const variants = await api("/catalogo");
  let forms = "";
  if (scope === "cliente" && variants.length) forms = `<div class="two-columns result"><article class="panel"><h2>Nuevo pedido</h2><form id="new-order" class="form-grid"><label>Producto<select name="variant_id">${variants.map((x) => `<option value="${x.id_variante}">${escapeHtml(x.producto)} · ${escapeHtml(x.codigo)} · C$ ${escapeHtml(x.precio_detalle)}</option>`).join("")}</select></label><label>Cantidad<input name="quantity" type="number" min="1" value="1" required></label><label>Entrega<select name="delivery_mode"><option>RETIRO</option><option>ENVIO</option></select></label><button>Crear pedido</button></form></article><article class="panel"><h2>Nueva cotización</h2><form id="new-quote" class="form-grid"><label>Producto<select name="variant_id">${variants.map((x) => `<option value="${x.id_variante}">${escapeHtml(x.producto)} · ${escapeHtml(x.codigo)}</option>`).join("")}</select></label><label>Cantidad<input name="quantity" type="number" min="1" value="1" required></label><label>Personalización<textarea name="customization"></textarea></label><button>Solicitar cotización</button></form></article></div>`;
  setContent("Catálogo", `<div class="cards">${variants.map((x) => `<article class="product-card"><span>${escapeHtml(x.categoria)}</span><h3>${escapeHtml(x.producto)}</h3><p>${escapeHtml(x.codigo)}</p><strong>C$ ${escapeHtml(x.precio_detalle)}</strong></article>`).join("")}</div>${forms}`);
  $("#new-order")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/pedidos", { method:"POST", body:JSON.stringify({ lines:[{ variant_id:+x.variant_id, quantity:+x.quantity, promotion_id:null }], delivery_mode:x.delivery_mode }) }); notice("Pedido creado"); } catch(error){ notice(error.message,true); } });
  $("#new-quote")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/cotizaciones", { method:"POST", body:JSON.stringify({ lines:[{ variant_id:+x.variant_id, quantity:+x.quantity, customization:x.customization || null }], observations:null }) }); notice("Cotización creada"); } catch(error){ notice(error.message,true); } });
}

async function payments() {
  let rows;
  let orderRows = [];
  if (scope === "cliente") {
    orderRows = await api("/pedidos");
    const groups = await Promise.all(orderRows.map((order) => api(`/pagos/pedidos/${order.id_pedido}`)));
    rows = groups.flat();
  } else rows = await api("/pagos");
  let report = "";
  if (scope === "cliente" && orderRows.length) report = `<article class="panel result"><h2>Reportar pago</h2><form id="report-payment" class="form-grid inline"><label>Pedido<select name="order_id">${orderRows.map((x) => `<option value="${x.id_pedido}">${escapeHtml(x.codigo_pedido)} · ${escapeHtml(x.estado)}</option>`).join("")}</select></label><label>Hito<select name="milestone_number"><option value="1">Anticipo</option><option value="2">Saldo</option></select></label><label>Método<select name="method"><option>TRANSFERENCIA</option><option>EFECTIVO</option><option>TARJETA</option><option>OTRO</option></select></label><label>Referencia<input name="reference"></label><button>Reportar para revisión</button></form></article>`;
  let actions = "";
  if (permitted("PAGO_VERIFICAR") && rows.some((x) => x.estado_verificacion === "PENDIENTE")) actions = `<article class="panel result"><h2>Resolver pago</h2><form id="payment-action" class="form-grid inline"><label>Pago<select name="id">${rows.filter((x) => x.estado_verificacion === "PENDIENTE").map((x) => `<option value="${x.id_transaccion}">#${x.id_transaccion} · pedido ${x.id_pedido} · C$ ${escapeHtml(x.monto_con_signo)}</option>`).join("")}</select></label><label>Decisión<select name="action"><option value="confirmar">Confirmar</option><option value="rechazar">Rechazar</option></select></label><label>Motivo<input name="reason" value="Revisión manual"></label><button>Guardar</button></form></article>`;
  setContent("Pagos", table(rows) + report + actions);
  $("#report-payment")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/pagos/pedidos/${x.order_id}/reportar`, { method:"POST", body:JSON.stringify({ milestone_number:+x.milestone_number, idempotency_key:crypto.randomUUID(), method:x.method, bank:null, reference:x.reference || null }) }); notice("Pago reportado para revisión"); await payments(); } catch(error){ notice(error.message,true); } });
  $("#payment-action")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/pagos/${x.id}/${x.action}`, { method:"POST", body:x.action === "rechazar" ? JSON.stringify({ reason:x.reason }) : undefined }); notice("Pago resuelto"); await payments(); } catch(error){ notice(error.message,true); } });
}

async function inventory() { setContent("Inventario", table(await api("/inventario/articulos"))); }

async function purchases() {
  const [rows, providers, articles] = await Promise.all([api("/compras"), api("/compras/proveedores"), api("/inventario/articulos")]);
  let create = "";
  if (permitted("COMPRA_REGISTRAR")) create = `<article class="panel result"><h2>Nueva compra</h2><form id="new-purchase" class="form-grid inline"><label>Proveedor<select name="provider_id">${options(providers,"id_proveedor","nombre")}</select></label><label>Artículo<select name="article_id">${options(articles,"id_articulo","nombre")}</select></label><label>Cantidad<input name="quantity" type="number" min=".001" step=".001" required></label><label>Costo unitario<input name="unit_cost" type="number" min="0" step=".01" required></label><label>Documento<input name="document_number"></label><button>Crear borrador</button></form></article>`;
  let confirm = "";
  if (permitted("COMPRA_AUTORIZAR") && rows.some((x) => x.estado === "BORRADOR")) confirm = `<article class="panel result"><h2>Autorizar entrada</h2><form id="confirm-purchase" class="form-grid inline"><label>Compra revisada<select name="id">${rows.filter((x) => x.estado === "BORRADOR").map((x) => `<option value="${x.id_compra}">#${x.id_compra} · C$ ${escapeHtml(x.total_compra)}</option>`).join("")}</select></label><button>Confirmar una vez</button></form></article>`;
  setContent("Compras", table(rows) + create + confirm);
  $("#new-purchase")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/compras", { method:"POST", body:JSON.stringify({ provider_id:+x.provider_id, document_number:x.document_number || null, lines:[{ article_id:+x.article_id, quantity:x.quantity, unit_cost:x.unit_cost }] }) }); notice("Compra creada en borrador"); await purchases(); } catch(error){ notice(error.message,true); } });
  $("#confirm-purchase")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/compras/${x.id}/confirmar`, { method:"POST" }); notice("Compra confirmada e inventario actualizado"); await purchases(); } catch(error){ notice(error.message,true); } });
}

async function providers() {
  const rows = await api("/compras/proveedores");
  const form = permitted("PROVEEDOR_GESTIONAR") ? `<article class="panel result"><h2>Nuevo proveedor</h2><form id="new-provider" class="form-grid inline"><label>Nombre<input name="name" required></label><label>Correo<input name="email" type="email"></label><label>Teléfono<input name="phone"></label><label>Dirección<input name="address"></label><button>Registrar</button></form></article>` : "";
  setContent("Proveedores", table(rows) + form);
  $("#new-provider")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/compras/proveedores", { method:"POST", body:JSON.stringify({ name:x.name, email:x.email || null, phone:x.phone || null, address:x.address || null }) }); notice("Proveedor registrado"); await providers(); } catch(error){ notice(error.message,true); } });
}

async function losses() {
  const rows = await api("/perdidas");
  let form = "";
  if (permitted("PERDIDA_REGISTRAR")) { const articles=await api("/inventario/articulos"); form=`<article class="panel result"><h2>Reportar pérdida operativa</h2><form id="new-loss" class="form-grid inline"><label>Artículo<select name="article_id">${options(articles,"id_articulo","nombre")}</select></label><label>Cantidad<input name="quantity" type="number" min=".001" step=".001" required></label><label>Motivo<input name="reason" required></label><button>Reportar y confirmar</button></form></article>`; }
  setContent(scope === "produccion" ? "Incidencias operativas" : "Pérdidas", table(rows) + form);
  $("#new-loss")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { const loss=await api("/perdidas", { method:"POST", body:JSON.stringify({ moment:"FUERA_PRODUCCION", incident_type:"DANO_ALMACENAMIENTO", reason:x.reason, order_id:null, stage_id:null, description:"Registrada desde el panel" }) }); await api(`/perdidas/${loss.id_perdida}/confirmar`, { method:"POST", body:JSON.stringify({ lines:[{ article_id:+x.article_id, quantity:x.quantity, damage_description:x.reason }] }) }); notice("Pérdida confirmada"); await losses(); } catch(error){ notice(error.message,true); } });
}

async function reports() { const report=await api("/reportes/resumen"); setContent("Reportes financieros", `<h2>Ingresos verificados</h2><div class="metrics"><article class="metric"><strong>C$ ${escapeHtml(report.ingresos_verificados)}</strong></article></div><h2>Compras por proveedor</h2>${table(report.compras_por_proveedor)}<h2>Pérdidas principales</h2>${table(report.perdidas_principales)}<h2>Movimientos</h2>${table(report.movimientos_inventario)}`); }
async function clients() { setContent("Clientes", table(await api("/clientes"))); }

async function tracking() {
  const rows=await api("/pedidos");
  setContent("Seguimiento", `<article class="panel"><form id="track-order" class="form-grid inline"><label>Pedido<select name="id">${rows.map((x) => `<option value="${x.id_pedido}">${escapeHtml(x.codigo_pedido)} · ${escapeHtml(x.estado)}</option>`).join("")}</select></label><button>Ver historial</button></form></article><div id="tracking-result" class="result">${table(rows)}</div>`);
  $("#track-order").addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { $("#tracking-result").innerHTML=table(await api(`/pedidos/${x.id}/historial`)); } catch(error){ notice(error.message,true); } });
}

async function employees() {
  const [rows, roles] = await Promise.all([api("/empleados"), api("/empleados/roles")]);
  const roleOptions = options(roles,"id_rol","nombre");
  setContent("Empleados y roles", `${table(rows)}<div class="two-columns result"><article class="panel"><h2>Invitar empleado</h2><form id="invite-employee" class="form-grid"><label>Nombres<input name="names" required></label><label>Apellidos<input name="surnames"></label><label>Correo<input name="email" type="email" required></label><label>Teléfono<input name="phone"></label><label>Documento<input name="document"></label><label>Rol<select name="role_id">${roleOptions}</select></label><button>Enviar invitación segura</button></form></article><article class="panel"><h2>Cambiar rol</h2><form id="assign-role" class="form-grid"><label>Empleado<select name="employee_id">${rows.map((x) => `<option value="${x.id_persona}">${escapeHtml(x.nombre)} · ${escapeHtml(x.codigo_empleado)}</option>`).join("")}</select></label><label>Rol<select name="role_id">${roleOptions}</select></label><button>Asignar</button></form></article></div>`);
  $("#invite-employee").addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/empleados/invitaciones", { method:"POST", body:JSON.stringify({ ...x, role_id:+x.role_id, capacity:10, surnames:x.surnames || null, phone:x.phone || null, document:x.document || null }) }); notice("Invitación enviada; el empleado debe activar su acceso"); await employees(); } catch(error){ notice(error.message,true); } });
  $("#assign-role").addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/empleados/${x.employee_id}/rol`, { method:"PUT", body:JSON.stringify({ role_id:+x.role_id }) }); notice("Rol actualizado; será efectivo en la próxima consulta"); await employees(); } catch(error){ notice(error.message,true); } });
}

async function designs() {
  const rows = await api("/pedidos");
  const orderOptions=rows.map((x) => `<option value="${x.id_pedido}">${escapeHtml(x.codigo_pedido)} · ${escapeHtml(x.estado)}</option>`).join("");
  setContent("Diseños", `${table(rows)}<div class="two-columns result"><article class="panel"><h2>Nueva versión privada</h2><form id="upload-design" class="form-grid"><label>Pedido<select name="order_id">${orderOptions}</select></label><label>Línea<input name="line" type="number" min="1" value="1" required></label><label>Archivo<input name="file" type="file" accept="image/png,image/jpeg,application/pdf" required></label><button>Subir</button></form></article><article class="panel"><h2>Revisar versiones</h2><form id="load-designs" class="form-grid"><label>Pedido<select name="order_id">${orderOptions}</select></label><label>Línea<input name="line" type="number" min="1" value="1" required></label><button>Consultar versiones</button></form></article><article class="panel"><h2>Operación de producción</h2><form id="production-action" class="form-grid"><label>Pedido<select name="order_id">${orderOptions}</select></label><label>Operación<select name="action"><option value="start">Iniciar producción</option><option value="consume">Consumir reserva</option></select></label><button>Ejecutar</button></form></article></div><div id="design-versions" class="result"></div>`);
  $("#upload-design").addEventListener("submit", async (event) => { event.preventDefault(); const x=new FormData(event.target); const order=x.get("order_id"), line=x.get("line"); x.delete("order_id"); x.delete("line"); try { await api(`/disenos/pedidos/${order}/lineas/${line}/versiones`, { method:"POST", body:x }); notice("Versión de diseño almacenada"); } catch(error){ notice(error.message,true); } });
  $("#load-designs").addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { const versions=await api(`/disenos/pedidos/${x.order_id}/lineas/${x.line}/versiones`); $("#design-versions").innerHTML=`${table(versions)}${versions.length ? `<article class="panel result"><form id="design-decision" class="form-grid inline"><input type="hidden" name="order_id" value="${x.order_id}"><input type="hidden" name="line" value="${x.line}"><label>Versión<select name="version">${versions.map((v) => `<option value="${v.numero_version}">Versión ${v.numero_version} · ${escapeHtml(v.nombre_archivo)}</option>`).join("")}</select></label><label>Decisión<select name="approved"><option value="true">Aprobar</option><option value="false">Rechazar</option></select></label><button>Registrar decisión</button></form></article>` : ""}`; $("#design-decision")?.addEventListener("submit", async (decisionEvent) => { decisionEvent.preventDefault(); const d=fields(decisionEvent.target); try { await api(`/disenos/pedidos/${d.order_id}/lineas/${d.line}/versiones/${d.version}/decision`, { method:"POST", body:JSON.stringify({ approved:d.approved === "true", medium:"PORTAL" }) }); notice("Decisión de diseño registrada"); } catch(error){ notice(error.message,true); } }); } catch(error){ notice(error.message,true); } });
  $("#production-action").addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { const path=x.action === "start" ? `/produccion/pedidos/${x.order_id}/iniciar` : `/inventario/pedidos/${x.order_id}/consumir`; await api(path,{ method:"POST" }); notice("Operación de producción completada"); await designs(); } catch(error){ notice(error.message,true); } });
}
function profile() { setContent("Mi perfil", `<article class="panel"><dl><dt>Nombre</dt><dd>${escapeHtml(identity.nombre)}</dd><dt>Perfil</dt><dd>${escapeHtml(identity.tipo_perfil)}</dd><dt>Roles activos</dt><dd>${escapeHtml(identity.roles.join(", ") || "Cliente")}</dd><dt>Estado</dt><dd>${escapeHtml(identity.estado_cuenta)}</dd></dl></article>`); }

const loaders = { summary,orders,quotes,payments,catalog,inventory,purchases,providers,losses,reports,employees,clients,designs,tracking,profile };
async function navigate(view) {
  const item = (menus[scope] || []).find((entry) => entry[0] === view && (!entry[2] || permitted(entry[2])));
  if (!item) { location.assign(expectedDashboard); return; }
  history.replaceState(null,"",`${location.pathname}?view=${view}`);
  document.querySelectorAll("#menu a").forEach((link) => link.classList.toggle("active",link.dataset.view===view));
  try { await loaders[view](); } catch(error) { setContent(item[1],""); notice(error.message,true); }
}
async function start() {
  if (!accessToken()) { location.assign("/app/#acceso"); return; }
  try { identity=await api("/auth/me"); } catch(error) { sessionStorage.removeItem("s2r_access_token"); location.assign(`/app/#acceso`); return; }
  if (identity.dashboard_inicial !== expectedDashboard) { location.assign(identity.dashboard_inicial); return; }
  $("#user-name").textContent=identity.nombre;
  $("#user-role").textContent=identity.roles.join(" · ") || identity.tipo_perfil;
  $("#account-state").textContent=identity.estado_cuenta;
  const available=(menus[scope] || []).filter((entry) => !entry[2] || permitted(entry[2]));
  $("#menu").innerHTML=available.map((entry) => `<a href="?view=${entry[0]}" data-view="${entry[0]}">${escapeHtml(entry[1])}</a>`).join("");
  $("#menu").addEventListener("click", (event) => { const link=event.target.closest("a[data-view]"); if(link){ event.preventDefault(); navigate(link.dataset.view); } });
  const requested=new URLSearchParams(location.search).get("view");
  await navigate(available.some((entry) => entry[0]===requested) ? requested : available[0][0]);
}
$("#logout").addEventListener("click", () => { sessionStorage.removeItem("s2r_access_token"); location.assign("/app/"); });
start();
