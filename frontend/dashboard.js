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
  try {
    return await AuthSession.requestJSON(fetch, `/api/v1${path}`, { ...options, headers });
  } catch (error) {
    if (error instanceof AuthSession.ApiError) error.message = UiPresentation.friendlyError(error.message, scope !== "cliente");
    throw error;
  }
}
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[char]));
const display = (value) => Array.isArray(value) ? value.join(", ") : typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "");
const formatCurrency = UiPresentation.money;
const fields = (form) => Object.fromEntries(new FormData(form).entries());
const permitted = (code) => identity.permisos.includes(code);
function prepareControls(root) {
  root.querySelectorAll("input:not([type=hidden]), textarea").forEach((control) => {
    if (!control.autocomplete) control.autocomplete = "off";
    if (control.type === "email") control.spellcheck = false;
  });
}
new MutationObserver(() => prepareControls($("#content"))).observe($("#content"), { childList:true, subtree:true });
function table(rows, columns, emptyMessage = "No hay información disponible.") {
  if (!rows.length) return `<div class="empty-state"><p>${escapeHtml(emptyMessage)}</p></div>`;
  if (!columns?.length) throw new Error("La tabla requiere columnas explícitas");
  return `<div class="table-wrap" role="region" aria-label="${escapeHtml(columns[0].region || "Información")}" tabindex="0"><table><thead><tr>${columns.map((column) => `<th scope="col">${escapeHtml(column.label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map((column) => `<td>${escapeHtml(column.format ? column.format(row[column.key], row) : display(row[column.key]))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
const columns = {
  orders: [
    { key:"codigo_pedido", label:"Pedido", region:"Pedidos" },
    { key:"fecha_creacion", label:"Fecha", format:(value) => UiPresentation.date(value) },
    { key:"estado", label:"Estado", format:UiPresentation.label },
    { key:"total_pedido", label:"Total", format:formatCurrency },
    { key:"vencimiento_pago", label:"Vencimiento", format:(value) => UiPresentation.date(value) },
  ],
  quotes: [
    { key:"id_cotizacion", label:"Cotización", region:"Cotizaciones", format:(value) => `COT-${String(value).padStart(6,"0")}` },
    { key:"fecha_emision", label:"Fecha", format:(value) => UiPresentation.date(value) },
    { key:"fecha_vencimiento", label:"Vence", format:(value) => UiPresentation.date(value) },
    { key:"estado", label:"Estado", format:UiPresentation.label },
    { key:"total_ofrecido", label:"Total", format:formatCurrency },
  ],
  payments: [
    { key:"codigo_pedido", label:"Pedido", region:"Pagos" },
    { key:"id_transaccion", label:"Referencia", format:(value) => `Pago ${value}` },
    { key:"monto_con_signo", label:"Monto", format:formatCurrency },
    { key:"estado_verificacion", label:"Estado", format:UiPresentation.label },
  ],
  inventory: [
    { key:"codigo", label:"Código", region:"Inventario" },
    { key:"nombre", label:"Artículo" },
    { key:"existencia_actual", label:"Existencia", format:(value,row) => UiPresentation.quantity(value,row.unidad_medida) },
    { key:"disponible", label:"Disponible", format:(value,row) => UiPresentation.quantity(value,row.unidad_medida) },
    { key:"existencia_minima", label:"Mínimo", format:(value,row) => UiPresentation.quantity(value,row.unidad_medida) },
    { key:"estado", label:"Estado", format:UiPresentation.label },
  ],
  movements: [
    { key:"fecha_hora", label:"Fecha", region:"Movimientos de inventario", format:(value) => UiPresentation.date(value,true) },
    { key:"tipo_movimiento", label:"Movimiento", format:UiPresentation.label },
    { key:"cantidad", label:"Cantidad", format:UiPresentation.quantity },
    { key:"motivo", label:"Motivo" },
  ],
  purchases: [
    { key:"id_compra", label:"Compra", region:"Compras", format:(value) => `Compra ${value}` },
    { key:"proveedor", label:"Proveedor" },
    { key:"fecha_compra", label:"Fecha", format:(value) => UiPresentation.date(value) },
    { key:"numero_documento", label:"Documento" },
    { key:"estado", label:"Estado", format:UiPresentation.label },
    { key:"total_compra", label:"Total", format:formatCurrency },
  ],
  providers: [
    { key:"nombre", label:"Proveedor", region:"Proveedores" },
    { key:"telefono", label:"Teléfono" },
    { key:"correo", label:"Correo" },
    { key:"estado", label:"Estado", format:UiPresentation.label },
  ],
  losses: [
    { key:"fecha_hora", label:"Fecha", region:"Pérdidas", format:(value) => UiPresentation.date(value,true) },
    { key:"tipo", label:"Incidente", format:UiPresentation.label },
    { key:"momento", label:"Momento", format:UiPresentation.label },
    { key:"motivo", label:"Motivo" },
    { key:"estado", label:"Estado", format:UiPresentation.label },
  ],
};
function options(rows, value, label) { return rows.map((row) => `<option value="${row[value]}">${escapeHtml(row[label])}</option>`).join(""); }
function setContent(title, html) { $("#view-title").textContent = title; $("#content").innerHTML = html; prepareControls($("#content")); }
const employeeActivationLabels = {
  PENDIENTE_ENVIO: "Pendiente de envío",
  PENDIENTE_ACTIVACION: "Solicitud aceptada / pendiente de activación",
  ACTIVA: "Activa",
  SUSPENDIDA: "Suspendida",
  INVITACION_FALLIDA: "Solicitud fallida",
};
function localDate(value) {
  return UiPresentation.date(value, true);
}
function employeeTable(rows) {
  if (!rows.length) return '<div class="panel"><p class="muted">No hay empleados para mostrar.</p></div>';
  return `<div class="table-wrap" role="region" aria-label="Empleados" tabindex="0"><table><thead><tr><th scope="col">Empleado</th><th scope="col">Correo</th><th scope="col">Rol</th><th scope="col">Activación</th><th scope="col">Estado laboral</th><th scope="col">Solicitud inicial</th><th scope="col">Acciones</th></tr></thead><tbody>${rows.map((row) => {
    const resend = row.puede_reenviar
      ? `<button type="button" class="secondary resend-invitation" data-employee-id="${row.id_persona}">Solicitar enlace nuevo</button>`
      : `<span class="muted">${row.estado_activacion === "PENDIENTE_ACTIVACION" || row.estado_activacion === "INVITACION_FALLIDA" || row.estado_activacion === "PENDIENTE_ENVIO" ? `Reenvío disponible ${escapeHtml(localDate(row.reenvio_disponible_desde))}` : "Sin acciones de activación"}</span>`;
    return `<tr><td><strong>${escapeHtml(row.nombre)}</strong><br><span class="muted">${escapeHtml(row.codigo_empleado)}</span></td><td>${escapeHtml(row.correo)}</td><td>${escapeHtml((row.roles || []).join(", ") || "Sin rol")}</td><td><span class="status status-${escapeHtml(row.estado_activacion.toLowerCase())}">${escapeHtml(employeeActivationLabels[row.estado_activacion] || row.estado_activacion)}</span></td><td>${escapeHtml(row.estado_laboral)}</td><td>${escapeHtml(localDate(row.fecha_invitacion))}</td><td>${resend}</td></tr>`;
  }).join("")}</tbody></table></div>`;
}
function clientDetailHtml(client) {
  const canManage = permitted("EMPLEADO_GESTIONAR");
  const edit = canManage ? `<article class="panel"><h3>Editar datos autorizados</h3><form id="edit-client" class="form-grid"><label>Nombres<input name="names" value="${escapeHtml(client.nombres)}" required></label><label>Apellidos<input name="surnames" value="${escapeHtml(client.apellidos)}"></label><label>Teléfono<input name="phone" type="tel" value="${escapeHtml(client.telefono)}"></label><label>Documento<input name="document" value="${escapeHtml(client.documento)}"></label><label>Dirección habitual<textarea name="usual_address">${escapeHtml(client.direccion_habitual)}</textarea></label><button>Guardar ficha</button></form></article>` : "";
  const wholesale = canManage && client.tipo_cliente !== "INVITADO" ? `<article class="panel"><h3>Condición mayorista</h3><form id="wholesale-client" class="form-grid"><label>Decisión<select name="enabled"><option value="true">Autorizar MAYORISTA</option><option value="false">Revocar y usar DETALLE</option></select></label><label>Motivo<input name="reason" minlength="3" required></label><button>Registrar decisión</button></form><p class="muted">La decisión no modifica precios ya pactados en pedidos.</p></article>` : "";
  return `<article class="panel"><h2>${escapeHtml(client.nombre)}</h2><dl><dt>Referencia</dt><dd>Cliente ${escapeHtml(client.id_persona)}</dd><dt>Correo</dt><dd>${escapeHtml(client.correo || "—")}</dd><dt>Teléfono</dt><dd>${escapeHtml(client.telefono || "—")}</dd><dt>Dirección habitual</dt><dd>${escapeHtml(client.direccion_habitual || "—")}</dd><dt>Tipo</dt><dd>${escapeHtml(UiPresentation.label(client.tipo_cliente))}</dd><dt>Condición comercial</dt><dd><span class="status">${escapeHtml(UiPresentation.label(client.condicion_comercial))}</span></dd><dt>Estado</dt><dd>${escapeHtml(UiPresentation.label(client.estado))}</dd></dl></article><div class="two-columns result">${edit}${wholesale}</div><h3>Pedidos</h3>${table(client.pedidos,[{key:"codigo",label:"Pedido",region:"Pedidos del cliente"},{key:"fecha",label:"Fecha",format:(value)=>UiPresentation.date(value)},{key:"estado",label:"Estado",format:UiPresentation.label},{key:"total",label:"Total",format:formatCurrency}],"Este cliente todavía no tiene pedidos.")}<h3>Historial administrativo</h3>${table(client.historial,[{key:"fecha",label:"Fecha",region:"Historial administrativo",format:(value)=>UiPresentation.date(value,true)},{key:"accion",label:"Acción",format:UiPresentation.label},{key:"motivo",label:"Motivo"}],"No hay cambios administrativos registrados.")}`;
}

const menus = {
  cliente: [["summary","Resumen"],["orders","Mis pedidos"],["quotes","Mis cotizaciones"],["payments","Pagos"],["catalog","Catálogo"],["tracking","Seguimiento"],["profile","Mi perfil"]],
  admin: [["summary","Resumen"],["orders","Pedidos","PEDIDO_GESTIONAR"],["quotes","Cotizaciones","PEDIDO_GESTIONAR"],["clients","Clientes","PEDIDO_GESTIONAR"],["catalog","Catálogo y recetas","CATALOGO_GESTIONAR"],["inventory","Inventario","INVENTARIO_CONSULTAR"],["purchases","Compras","COMPRA_CONSULTAR"],["providers","Proveedores","PROVEEDOR_CONSULTAR"],["payments","Pagos","PAGO_CONSULTAR"],["losses","Pérdidas","PERDIDA_CONSULTAR"],["reports","Reportes","REPORTE_FINANCIERO_CONSULTAR"],["employees","Empleados y roles","EMPLEADO_GESTIONAR"],["profile","Mi perfil"]],
  contabilidad: [["summary","Resumen financiero","REPORTE_FINANCIERO_CONSULTAR"],["payments","Ingresos verificados","PAGO_CONSULTAR"],["purchases","Compras","COMPRA_CONSULTAR"],["inventory","Inventario","INVENTARIO_CONSULTAR"],["losses","Pérdidas","PERDIDA_CONSULTAR"],["reports","Reportes","REPORTE_FINANCIERO_CONSULTAR"],["profile","Mi perfil"]],
  ventas: [["clients","Clientes","PEDIDO_GESTIONAR"],["quotes","Cotizaciones","PEDIDO_GESTIONAR"],["orders","Pedidos","PEDIDO_GESTIONAR"],["payments","Pagos","PAGO_CONSULTAR"],["catalog","Productos"],["profile","Mi perfil"]],
  produccion: [["designs","Diseños","DISENO_APROBAR"],["orders","Pedidos","PEDIDO_GESTIONAR"],["inventory","Inventario","INVENTARIO_CONSULTAR"],["losses","Incidencias","PERDIDA_CONSULTAR"],["profile","Mi perfil"]]
};
const productionPermissions = {
  INICIAR_PRODUCCION: "PRODUCCION_INICIAR",
  CONSUMIR_RESERVAS: "INVENTARIO_CONSUMIR_RESERVAS",
  COMPLETAR_PRODUCCION: "PRODUCCION_INICIAR",
};

function productLines(lines) {
  return `<ul class="product-lines">${lines.map((line) => `<li><span><strong>${escapeHtml(line.producto)}</strong><small>${escapeHtml(line.variante)}</small></span><span>${escapeHtml(UiPresentation.quantity(line.cantidad))} × ${escapeHtml(formatCurrency(line.precio_unitario))}</span></li>`).join("")}</ul>`;
}

function orderCard(order, { compact = false } = {}) {
  return `<article class="order-card">
    <header><div><p class="section-kicker">${escapeHtml(UiPresentation.orderMessage(order.estado))}</p><h2>${escapeHtml(order.codigo)}</h2></div><span class="status status-${escapeHtml(order.estado.toLowerCase())}">${escapeHtml(UiPresentation.label(order.estado))}</span></header>
    ${compact ? "" : productLines(order.productos)}
    <dl class="order-facts"><div><dt>Fecha</dt><dd>${escapeHtml(UiPresentation.date(order.fecha))}</dd></div><div><dt>Total</dt><dd>${escapeHtml(formatCurrency(order.total))}</dd></div><div><dt>Pagado</dt><dd>${escapeHtml(formatCurrency(order.pagado))}</dd></div><div><dt>Saldo</dt><dd>${escapeHtml(formatCurrency(order.saldo_pendiente))}</dd></div><div><dt>Entrega</dt><dd>${escapeHtml(UiPresentation.label(order.modalidad_entrega))}</dd></div></dl>
    <footer><p><strong>Próxima acción:</strong> ${escapeHtml(UiPresentation.label(order.proxima_accion))}</p><button type="button" class="secondary order-detail" data-order-code="${escapeHtml(order.codigo)}">Ver detalle y seguimiento</button></footer>
  </article>`;
}

function orderProgress(order) {
  const stages = UiPresentation.orderProgressStages(order);
  const interrupted = ["CANCELADO","EXPIRADO","RECHAZADO"].includes(order.estado);
  return `${interrupted ? `<div class="context-alert"><strong>${escapeHtml(UiPresentation.label(order.estado))}</strong><p>Este pedido no continuará a las siguientes etapas.</p></div>` : ""}<ol class="order-progress" aria-label="Progreso del pedido" style="--progress-steps:${stages.length}">${stages.map(({ label, completed, current }) => `<li class="${completed ? "completed" : current && !interrupted ? "current" : "pending"}" ${current && !interrupted ? 'aria-current="step"' : ""}><span aria-hidden="true"></span><strong>${label}</strong></li>`).join("")}</ol>`;
}

async function showOrderDetail(code) {
  const order = await api(`/portal/pedidos/${encodeURIComponent(code)}`);
  const history = order.historial.length
    ? `<ol class="history-list">${order.historial.map((item) => `<li><time>${escapeHtml(UiPresentation.date(item.fecha,true))}</time><div><strong>${escapeHtml(UiPresentation.orderMessage(item.estado))}</strong>${item.detalle ? `<p>${escapeHtml(item.detalle)}</p>` : ""}</div></li>`).join("")}</ol>`
    : '<div class="empty-state"><p>Aún no hay novedades adicionales para este pedido.</p></div>';
  setContent(`Pedido ${order.codigo}`, `<button type="button" class="back-link secondary">← Volver a mis pedidos</button><article class="order-detail-view">${orderProgress(order)}${orderCard(order)}<section><div class="section-heading"><div><p class="section-kicker">Actualizaciones verificadas</p><h2>Historial del pedido</h2></div></div>${history}</section></article>`);
  $(".back-link").addEventListener("click", orders);
  $(".order-detail")?.remove();
}

function bindOrderDetails() {
  document.querySelectorAll(".order-detail").forEach((button) => button.addEventListener("click", () => showOrderDetail(button.dataset.orderCode).catch((error) => notice(error.message,true))));
}

async function summary() {
  if (scope === "cliente") {
    const data = await api("/portal/resumen");
    const featured = data.pedido_destacado
      ? orderCard(data.pedido_destacado, { compact:true })
      : `<article class="customer-feature"><div><p class="section-kicker">Hola, ${escapeHtml(identity.nombre)}</p><h2>Tu próxima idea empieza aquí</h2><p>Explora productos y solicita una cotización para crear algo personal.</p></div><button type="button" class="secondary feature-link" data-view="catalog">Explorar catálogo</button></article>`;
    setContent(`Hola, ${identity.nombre.split(" ")[0]}`, `<div class="customer-summary-grid"><section>${featured}</section><aside class="customer-actions"><h2>Lo que requiere tu atención</h2><a href="?view=payments" data-view="payments"><strong>${data.pagos_pendientes}</strong><span>Pagos en revisión</span></a><a href="?view=quotes" data-view="quotes"><strong>${data.cotizaciones_pendientes}</strong><span>Cotizaciones pendientes</span></a><a href="?view=orders" data-view="orders"><strong>${data.pedidos_listos}</strong><span>Pedidos listos</span></a><a href="?view=catalog" data-view="catalog"><span>Explorar productos</span></a></aside></div><div class="metrics compact result"><article class="metric"><span>Pedidos activos</span><strong>${data.pedidos_activos}</strong></article><article class="metric"><span>Saldo pendiente</span><strong>${escapeHtml(formatCurrency(data.saldo_total))}</strong></article><article class="metric"><span>Pedidos listos</span><strong>${data.pedidos_listos}</strong></article></div>`);
    bindOrderDetails();
    $(".feature-link")?.addEventListener("click", (event) => navigate(event.currentTarget.dataset.view));
    document.querySelectorAll(".customer-actions a[data-view]").forEach((link) => link.addEventListener("click", (event) => { event.preventDefault(); navigate(link.dataset.view); }));
    return;
  }
  if (permitted("REPORTE_FINANCIERO_CONSULTAR")) {
    const report = await api("/reportes/resumen");
    setContent("Resumen", `<div class="metrics priority"><article class="metric"><span>Pedidos nuevos · ${report.periodo_dias} días</span><strong>${escapeHtml(report.indicadores_pedidos.nuevos)}</strong></article><article class="metric"><span>Ingreso verificado</span><strong>${escapeHtml(formatCurrency(report.ingresos_verificados))}</strong></article><article class="metric attention"><span>Pagos por revisar</span><strong>${escapeHtml(report.pagos_pendientes.cantidad)}</strong></article><article class="metric attention"><span>Entregas pendientes</span><strong>${escapeHtml(report.entregas_pendientes)}</strong></article><article class="metric attention"><span>Stock bajo</span><strong>${report.stock_bajo.length}</strong></article></div><div class="operations-grid result"><section><div class="section-heading"><div><p class="section-kicker">Operación</p><h2>Pedidos por estado</h2></div></div>${table(report.pedidos_por_estado,[{key:"estado",label:"Estado",region:"Pedidos por estado",format:UiPresentation.label},{key:"cantidad",label:"Cantidad"}],"No hay pedidos recientes.")}</section><section><div class="section-heading"><div><p class="section-kicker">Últimos movimientos</p><h2>Actividad reciente</h2></div></div>${table(report.actividad_reciente,[{key:"fecha_hora",label:"Fecha",region:"Actividad reciente",format:(value)=>UiPresentation.date(value,true)},{key:"accion",label:"Actividad",format:UiPresentation.label},{key:"referencia_objeto",label:"Referencia"}],"No hay actividad reciente.")}</section></div><details class="report-details result"><summary>Ver indicadores complementarios</summary><div class="metrics compact"><article class="metric"><span>Pendientes de pago</span><strong>${escapeHtml(report.indicadores_pedidos.pendientes_pago)}</strong></article><article class="metric"><span>En diseño</span><strong>${escapeHtml(report.indicadores_pedidos.en_diseno)}</strong></article><article class="metric"><span>En producción</span><strong>${escapeHtml(report.indicadores_pedidos.en_produccion)}</strong></article><article class="metric"><span>Listos</span><strong>${escapeHtml(report.indicadores_pedidos.listos)}</strong></article></div><h2>Productos más vendidos</h2>${table(report.productos_mas_vendidos,[{key:"producto",label:"Producto",region:"Productos más vendidos"},{key:"unidades",label:"Unidades",format:UiPresentation.quantity}],"Todavía no hay ventas para este periodo.")}<h2>Pérdidas recientes</h2>${table(report.perdidas_principales,[{key:"nombre",label:"Artículo",region:"Pérdidas recientes"},{key:"cantidad_perdida",label:"Cantidad",format:UiPresentation.quantity},{key:"costo_perdida",label:"Costo",format:formatCurrency}],"No se registraron pérdidas en este periodo.")}</details>`);
  } else {
    const orders = await api("/pedidos");
    setContent("Trabajo pendiente", `<div class="metrics"><article class="metric"><span>Pedidos visibles</span><strong>${orders.length}</strong></article><article class="metric"><span>En producción</span><strong>${orders.filter((x) => x.estado === "EN_PRODUCCION").length}</strong></article></div>${table(orders,columns.orders,"No hay pedidos esperando trabajo.")}`);
  }
}

async function orders() {
  if (scope === "cliente") {
    const rows = await api("/portal/pedidos");
    setContent("Mis pedidos", rows.length
      ? `<div class="order-list">${rows.map((order) => orderCard(order)).join("")}</div>`
      : '<div class="empty-state customer-empty"><h2>Todavía no tienes pedidos</h2><p>Explora el catálogo para comenzar una personalización.</p><button type="button" class="primary-link empty-action">Ver catálogo</button></div>');
    bindOrderDetails();
    $(".empty-action")?.addEventListener("click", () => navigate("catalog"));
    return;
  }
  const rows = await api("/pedidos");
  const orderOptions = rows.map((x) => `<option value="${x.id_pedido}">${escapeHtml(x.codigo_pedido)} · ${escapeHtml(x.estado)}</option>`).join("");
  let forms = "";
  if (permitted("PEDIDO_GESTIONAR") && rows.length) {
    const summaries = await Promise.all(rows.map((x) => api(`/pedidos/${x.id_pedido}/operacion`)));
    const actionMap = { INICIAR_DISENO:["design","Iniciar diseño"], INICIAR_PRODUCCION:["start","Iniciar producción"], CONSUMIR_RESERVAS:["consume","Consumir reservas"], COMPLETAR_PRODUCCION:["finish","Completar producción"], COMPLETAR_ENTREGA:["deliver","Completar entrega o retiro"] };
    const allowedActions = summaries.flatMap((x) => { const action=actionMap[x.siguiente_accion]; const requiredPermission=productionPermissions[x.siguiente_accion]; if (!action || (requiredPermission && (!permitted(requiredPermission) || !x.produccion.acciones_permitidas.includes(x.siguiente_accion)))) return []; return [{ id:x.pedido.id_pedido, code:x.pedido.codigo_pedido, next:x.siguiente_accion, action:action[0], label:action[1] }]; });
    const actionForm = allowedActions.length ? `<article class="panel"><h2>Operación permitida</h2><form id="order-operation" class="form-grid"><label>Pedido y acción<select name="operation">${allowedActions.map((x) => `<option value="${x.id}:${x.action}">${escapeHtml(x.code)} · ${escapeHtml(x.label)}</option>`).join("")}</select></label><label>Motivo<input name="reason" value="Operación verificada desde el panel" required></label><button>Ejecutar</button></form></article>` : '<article class="panel"><h2>Operación permitida</h2><p class="muted">No hay transiciones administrativas disponibles.</p></article>';
    const deliveryOrders = summaries.filter((x) => x.pedido.modalidad_entrega === "ENVIO" && !x.entrega.id_envio && !["CANCELADO","EXPIRADO","ENTREGADO"].includes(x.pedido.estado));
    const deliveryForm = deliveryOrders.length ? `<article class="panel"><h2>Programar envío</h2><form id="delivery-schedule" class="form-grid"><label>Pedido<select name="id">${deliveryOrders.map((x) => `<option value="${x.pedido.id_pedido}">${escapeHtml(x.pedido.codigo_pedido)}</option>`).join("")}</select></label><label>Dirección<input name="address" required></label><label>Persona receptora<input name="recipient_name" required></label><label>Teléfono<input name="recipient_phone" type="tel"></label><button>Programar</button></form><p class="muted">Los datos habituales se completan al elegir el pedido y pueden modificarse para este envío.</p></article>` : "";
    forms = `<h2>Estado operativo</h2>${table(summaries.map((x) => ({ pedido:x.pedido.codigo_pedido, estado:x.pedido.estado, siguiente_accion:x.siguiente_accion, anticipo_verificado:x.pago.anticipo_verificado, saldo:x.pago.saldo_pendiente, reservas:x.inventario.reservas.length, entrega:x.entrega.estado || "SIN PROGRAMAR" })),[{key:"pedido",label:"Pedido",region:"Estado operativo"},{key:"estado",label:"Estado",format:UiPresentation.label},{key:"siguiente_accion",label:"Próxima acción",format:UiPresentation.label},{key:"saldo",label:"Saldo",format:formatCurrency},{key:"reservas",label:"Reservas"},{key:"entrega",label:"Entrega",format:UiPresentation.label}],"No hay pedidos que requieran atención.")}<div class="two-columns result">${actionForm}<article class="panel"><h2>Detalle integral</h2><form id="order-summary" class="form-grid"><label>Pedido<select name="id">${orderOptions}</select></label><button>Consultar hitos y reservas</button></form><div id="order-summary-result" class="result"></div></article>${deliveryForm}</div>`;
  }
  setContent("Pedidos", table(rows,columns.orders,"No hay pedidos para mostrar.") + forms);
  $("#order-operation")?.addEventListener("submit", async (event) => {
    event.preventDefault(); const x = fields(event.target); const [id, action] = x.operation.split(":");
    const actions = {
      design: [`/pedidos/${id}/estado`, { target:"EN_DISENO", reason:x.reason }],
      start: [`/produccion/pedidos/${id}/iniciar`, null],
      consume: [`/inventario/pedidos/${id}/consumir`, null],
      finish: [`/produccion/pedidos/${id}/completar`, null],
      deliver: [`/entregas/pedidos/${id}/completar`, { reason:x.reason }],
    };
    try { const [path, payload] = actions[action]; await api(path, { method:"POST", body:payload ? JSON.stringify(payload) : undefined }); notice("Operación registrada"); await orders(); } catch(error) { notice(error.message,true); }
  });
  $("#order-summary")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { const data=await api(`/pedidos/${x.id}/operacion`); $("#order-summary-result").innerHTML=`<p><strong>Siguiente acción:</strong> ${escapeHtml(UiPresentation.label(data.siguiente_accion))}</p><h3>Pagos</h3>${table(data.pago.hitos,[{key:"tipo_hito",label:"Hito",region:"Hitos de pago",format:UiPresentation.label},{key:"monto_exigido",label:"Exigido",format:formatCurrency},{key:"monto_verificado",label:"Verificado",format:formatCurrency},{key:"monto_restante",label:"Pendiente",format:formatCurrency},{key:"estado",label:"Estado",format:UiPresentation.label}],"No hay hitos de pago.")}<h3>Reservas</h3>${table(data.inventario.reservas,[{key:"articulo",label:"Material",region:"Reservas"},{key:"cantidad_reservada",label:"Reservado",format:UiPresentation.quantity},{key:"cantidad_pendiente",label:"Pendiente",format:UiPresentation.quantity},{key:"estado",label:"Estado",format:UiPresentation.label}],"No hay reservas para este pedido.")}`; } catch(error){ notice(error.message,true); } });
  $("#delivery-schedule")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/entregas/pedidos/${x.id}`, { method:"POST", body:JSON.stringify({ agency_id:null, address:x.address, recipient_name:x.recipient_name, recipient_phone:x.recipient_phone || null, agreed_fee:"0.00", scheduled_at:null }) }); notice("Envío programado"); } catch(error){ notice(error.message,true); } });
  const deliveryForm = $("#delivery-schedule");
  async function fillDeliveryDefaults() { if (!deliveryForm) return; const data=await api(`/entregas/pedidos/${deliveryForm.elements.id.value}/datos-iniciales`); deliveryForm.elements.recipient_name.value=data.nombre_receptor || ""; deliveryForm.elements.recipient_phone.value=data.telefono_receptor || ""; deliveryForm.elements.address.value=data.direccion_habitual || ""; }
  deliveryForm?.elements.id.addEventListener("change", () => fillDeliveryDefaults().catch((error) => notice(error.message,true)));
  if (deliveryForm) await fillDeliveryDefaults();
}

async function quotes() {
  if (scope === "cliente") {
    const rows = await api("/portal/cotizaciones");
    setContent("Mis cotizaciones", rows.length
      ? `<div class="quote-list">${rows.map((quote) => `<article class="quote-card"><header><div><p class="section-kicker">${escapeHtml(UiPresentation.label(quote.estado))}</p><h2>${escapeHtml(quote.referencia)}</h2></div><strong>${escapeHtml(formatCurrency(quote.total))}</strong></header>${productLines(quote.productos)}<p class="muted">Emitida ${escapeHtml(UiPresentation.date(quote.fecha))} · válida hasta ${escapeHtml(UiPresentation.date(quote.vencimiento))}</p>${quote.estado === "EMITIDA" ? `<div class="quote-actions"><button type="button" data-reference="${escapeHtml(quote.referencia)}" data-decision="ACEPTADA">Aceptar cotización</button><button type="button" class="secondary" data-reference="${escapeHtml(quote.referencia)}" data-decision="RECHAZADA">Rechazar</button></div>` : quote.estado === "ACEPTADA" ? `<button type="button" data-reference="${escapeHtml(quote.referencia)}" data-decision="CONVERTIR">Convertir en pedido</button>` : ""}</article>`).join("")}</div>`
      : '<div class="empty-state customer-empty"><h2>Aún no has solicitado una cotización</h2><p>Elige un producto y cuéntanos cómo quieres personalizarlo.</p><button type="button" class="empty-action">Explorar catálogo</button></div>');
    $(".empty-action")?.addEventListener("click", () => navigate("catalog"));
    document.querySelectorAll("[data-decision]").forEach((button) => button.addEventListener("click", async () => {
      const converting=button.dataset.decision === "CONVERTIR";
      if ((button.dataset.decision === "RECHAZADA" || converting) && !confirm(converting ? "¿Convertir esta cotización en un pedido?" : "¿Rechazar esta cotización?")) return;
      try {
        if (converting) await api(`/portal/cotizaciones/${encodeURIComponent(button.dataset.reference)}/convertir`, { method:"POST" });
        else await api(`/portal/cotizaciones/${encodeURIComponent(button.dataset.reference)}/decision`, { method:"POST", body:JSON.stringify({ decision:button.dataset.decision, reason:button.dataset.decision === "ACEPTADA" ? "Cliente acepta la cotización" : "Cliente rechaza la cotización" }) });
        notice(converting ? "Cotización convertida en pedido" : "Decisión registrada"); await quotes();
      } catch(error) { notice(error.message,true); }
    }));
    return;
  }
  const rows = await api("/cotizaciones");
  setContent("Cotizaciones", table(rows,columns.quotes,"No hay cotizaciones para mostrar."));
}

async function clientCatalog() {
  const variants = await api("/portal/catalogo");
  const glyphs = ["✦", "○", "◇", "⌁"];
  setContent("Catálogo", variants.length ? `<div class="catalog-intro"><div><p class="section-kicker">Personaliza a tu manera</p><h2>Elige un producto</h2><p>El precio se consulta en el servidor según tu cuenta y la cantidad seleccionada.</p></div></div><div class="customer-catalog">${variants.map((item,index) => `<article class="catalog-card"><div class="product-media tone-${(index % 4) + 1}" aria-hidden="true"><span class="product-glyph">${glyphs[index % glyphs.length]}</span></div><div class="catalog-card-body"><span class="product-category">${escapeHtml(item.categoria)}</span><h2>${escapeHtml(item.producto)}</h2><p>${escapeHtml(item.descripcion)}</p><p class="variant-name"><strong>Variante:</strong> ${escapeHtml(item.variante)}</p><p class="availability">${escapeHtml(UiPresentation.label(item.disponibilidad))}</p><strong class="price-preview" aria-live="polite">${escapeHtml(formatCurrency(item.precio_referencia))}</strong><form class="catalog-action" data-variant-id="${item.id_variante}"><label>Cantidad<input name="quantity" type="number" min="1" max="10000" value="1" required></label><label>Entrega<select name="delivery_mode"><option value="RETIRO">Retiro en tienda</option><option value="ENVIO">Envío</option></select></label><label class="full-field">Personalización para cotizar<textarea name="customization" placeholder="Ejemplo: nombre, colores y fecha…"></textarea></label><div class="catalog-buttons full-field"><button name="action" value="order" type="submit">Comprar</button><button name="action" value="quote" type="submit" class="secondary">Solicitar cotización</button></div></form></div></article>`).join("")}</div>` : '<div class="empty-state customer-empty"><h2>El catálogo está en preparación</h2><p>Vuelve pronto para descubrir nuevos productos.</p></div>');
  async function refreshPrice(form) {
    const preview=form.closest(".catalog-card").querySelector(".price-preview");
    preview.textContent="Consultando precio…";
    try {
      const price=await api(`/portal/catalogo/${form.dataset.variantId}/precio?cantidad=${encodeURIComponent(form.elements.quantity.value)}`);
      preview.textContent=`${formatCurrency(price.total)} total · ${formatCurrency(price.precio_unitario)} por unidad`;
    } catch(error) { preview.textContent=error.message; }
  }
  document.querySelectorAll(".catalog-action").forEach((form) => {
    form.elements.quantity.addEventListener("change", () => refreshPrice(form));
    refreshPrice(form);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data=fields(form); const action=event.submitter?.value;
      if (action === "order" && !confirm(`¿Crear un pedido de ${data.quantity} unidad(es)?`)) return;
      try {
        if (action === "order") {
          const created=await api("/portal/pedidos", { method:"POST", body:JSON.stringify({ lines:[{ variant_id:+form.dataset.variantId, quantity:+data.quantity, promotion_id:null }], delivery_mode:data.delivery_mode }) });
          notice(`Pedido ${created.codigo} creado correctamente`);
        } else {
          const created=await api("/portal/cotizaciones", { method:"POST", body:JSON.stringify({ lines:[{ variant_id:+form.dataset.variantId, quantity:+data.quantity, customization:data.customization || null }], observations:null }) });
          notice(`Cotización ${created.referencia} solicitada correctamente`);
        }
      } catch(error) { notice(error.message,true); }
    });
  });
}

async function catalog() {
  if (scope === "cliente") return clientCatalog();
  const variants = await api("/catalogo");
  let forms = "";
  if (permitted("CATALOGO_GESTIONAR")) {
    const [categories, products, adminVariants, articles] = await Promise.all([api("/catalogo/admin/categorias"), api("/catalogo/admin/productos"), api("/catalogo/admin/variantes"), api("/inventario/articulos")]);
    const categoryOptions = options(categories.filter((x) => x.estado === "ACTIVA"), "id_categoria", "nombre");
    const productOptions = options(products, "id_producto", "nombre");
    const variantOptions = adminVariants.map((x) => `<option value="${x.id_variante}">${escapeHtml(x.codigo_variante)}</option>`).join("");
    const stateActions = [...categories.map((x) => ({ value:`category:${x.id_categoria}:${x.estado === "ACTIVA" ? "INACTIVA" : "ACTIVA"}`, label:`Categoría ${x.nombre}: ${x.estado === "ACTIVA" ? "desactivar" : "activar"}` })), ...products.map((x) => ({ value:`product:${x.id_producto}:${x.estado_publicacion === "PUBLICADO" ? "INACTIVO" : "PUBLICADO"}`, label:`Producto ${x.nombre}: ${x.estado_publicacion === "PUBLICADO" ? "retirar" : "publicar"}` })), ...adminVariants.map((x) => ({ value:`variant:${x.id_variante}:${x.estado === "ACTIVA" ? "INACTIVA" : "ACTIVA"}`, label:`Variante ${x.codigo_variante}: ${x.estado === "ACTIVA" ? "desactivar" : "activar"}` }))];
    forms = `<h2>Mantenimiento</h2><div class="two-columns result"><article class="panel"><h3>Nueva categoría</h3><form id="new-category" class="form-grid"><label>Nombre<input name="name" required></label><label>Descripción<input name="description"></label><button>Crear categoría</button></form></article><article class="panel"><h3>Nuevo producto</h3><form id="new-product" class="form-grid"><label>Categoría<select name="category_id">${categoryOptions}</select></label><label>Nombre<input name="name" required></label><label>Información comercial<textarea name="commercial_information" required></textarea></label><button>Crear borrador</button></form></article><article class="panel"><h3>Nueva variante</h3><form id="new-variant" class="form-grid"><label>Producto<select name="product_id">${productOptions}</select></label><label>Código<input name="code" required></label><label>Precio detalle<input name="retail_price" type="number" min="0" step=".01" required></label><label><input name="requires_production" type="checkbox" checked> Requiere producción</label><button>Crear variante</button></form></article><article class="panel"><h3>Publicación y estados</h3><form id="catalog-state" class="form-grid"><label>Acción<select name="operation">${stateActions.map((x) => `<option value="${x.value}">${escapeHtml(x.label)}</option>`).join("")}</select></label><button>Aplicar</button></form></article><article class="panel"><h3>Composición</h3><form id="composition" class="form-grid"><label>Variante<select name="variant_id">${variantOptions}</select></label><label>Artículo<select name="article_id">${options(articles.filter((x) => x.estado === "ACTIVO"),"id_articulo","nombre")}</select></label><label>Cantidad estándar<input name="standard_quantity" type="number" min=".001" step=".001" required></label><label>Observación<input name="observations"></label><button>Guardar componente</button></form></article><article class="panel"><h3>Materiales y requerimientos</h3><form id="composition-tools" class="form-grid"><label>Variante<select name="variant_id">${variantOptions}</select></label><label>Artículo a retirar<select name="article_id">${options(articles,"id_articulo","nombre")}</select></label><label>Cantidad a producir<input name="quantity" type="number" min="1" value="1"></label><label>Acción<select name="action"><option value="requirements">Calcular materiales, costos y faltantes</option><option value="list">Ver receta, existencias y capacidad</option><option value="delete">Retirar componente seleccionado</option></select></label><button>Ejecutar</button></form><div id="composition-result" class="result"></div></article><article class="panel"><h3>Nueva escala mayorista</h3><form id="price-scale" class="form-grid"><label>Variante<select name="variant_id">${variantOptions}</select></label><label>Mínimo<input name="minimum_quantity" type="number" min="1" required></label><label>Máximo<input name="maximum_quantity" type="number" min="1"></label><label>Precio unitario<input name="wholesale_unit_price" type="number" min="0" step=".01" required></label><button>Crear escala con rango automático</button></form></article><article class="panel"><h3>Consultar y editar escalas</h3><form id="scale-query" class="form-grid"><label>Variante<select name="variant_id">${variantOptions}</select></label><button>Cargar escalas</button></form><div id="scale-result" class="result"></div></article></div><h2>Categorías</h2>${table(categories,[{key:"nombre",label:"Categoría",region:"Categorías"},{key:"descripcion",label:"Descripción"},{key:"estado",label:"Estado",format:UiPresentation.label}],"No hay categorías.")}<h2>Productos</h2>${table(products,[{key:"nombre",label:"Producto",region:"Productos"},{key:"informacion_comercial",label:"Información comercial"},{key:"estado_publicacion",label:"Publicación",format:UiPresentation.label}],"No hay productos.")}<h2>Variantes</h2>${table(adminVariants,[{key:"codigo_variante",label:"Variante",region:"Variantes"},{key:"caracteristicas",label:"Características"},{key:"precio_detalle",label:"Precio detalle",format:formatCurrency},{key:"estado",label:"Estado",format:UiPresentation.label}],"No hay variantes.")}`;
  }
  const glyphs = ["✦", "○", "◇", "⌁"];
  const cards = variants.length ? variants.map((x, index) => `<article class="product-card"><div class="product-media tone-${(index % 4) + 1}" aria-hidden="true"><span class="product-glyph">${glyphs[index % glyphs.length]}</span></div><div class="product-card-body"><span class="product-category">${escapeHtml(x.categoria)}</span><h3>${escapeHtml(x.producto)}</h3><p class="product-code">${escapeHtml(x.codigo)}</p><strong>${escapeHtml(formatCurrency(x.precio_detalle))}</strong></div></article>`).join("") : '<div class="empty-state"><h3>Sin productos publicados</h3><p>El catálogo se actualizará cuando haya variantes disponibles.</p></div>';
  setContent("Catálogo", `<div class="cards">${cards}</div>${forms}`);
  $("#new-order")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/pedidos", { method:"POST", body:JSON.stringify({ lines:[{ variant_id:+x.variant_id, quantity:+x.quantity, promotion_id:null }], delivery_mode:x.delivery_mode }) }); notice("Pedido creado"); } catch(error){ notice(error.message,true); } });
  $("#new-quote")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/cotizaciones", { method:"POST", body:JSON.stringify({ lines:[{ variant_id:+x.variant_id, quantity:+x.quantity, customization:x.customization || null }], observations:null }) }); notice("Cotización creada"); } catch(error){ notice(error.message,true); } });
  $("#new-category")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/catalogo/admin/categorias", { method:"POST", body:JSON.stringify({ name:x.name, description:x.description || null }) }); notice("Categoría creada"); await catalog(); } catch(error){ notice(error.message,true); } });
  $("#new-product")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/catalogo/admin/productos", { method:"POST", body:JSON.stringify({ category_id:+x.category_id, name:x.name, description:null, commercial_information:x.commercial_information, publication_state:"BORRADOR" }) }); notice("Producto creado en borrador"); await catalog(); } catch(error){ notice(error.message,true); } });
  $("#new-variant")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/catalogo/admin/variantes", { method:"POST", body:JSON.stringify({ product_id:+x.product_id, code:x.code, features:null, retail_price:x.retail_price, requires_production:event.target.requires_production.checked }) }); notice("Variante creada"); await catalog(); } catch(error){ notice(error.message,true); } });
  $("#catalog-state")?.addEventListener("submit", async (event) => { event.preventDefault(); const [type,id,state]=fields(event.target).operation.split(":"); const routes={ category:[`/catalogo/admin/categorias/${id}`,{ state }], product:[`/catalogo/admin/productos/${id}`,{ publication_state:state }], variant:[`/catalogo/admin/variantes/${id}`,{ state }] }; try { const [path,payload]=routes[type]; await api(path,{ method:"PATCH",body:JSON.stringify(payload) }); notice("Estado del catálogo actualizado"); await catalog(); } catch(error){ notice(error.message,true); } });
  $("#composition")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/catalogo/admin/variantes/${x.variant_id}/composicion/${x.article_id}`, { method:"PUT", body:JSON.stringify({ standard_quantity:x.standard_quantity, observations:x.observations || "" }) }); notice("Composición actualizada"); } catch(error){ notice(error.message,true); } });
  $("#composition-tools")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { if (x.action === "delete") { if(!confirm("¿Retirar este material de la receta?"))return; await api(`/catalogo/admin/variantes/${x.variant_id}/composicion/${x.article_id}`, { method:"DELETE" }); notice("Componente retirado"); await catalog(); return; } const path=x.action === "list" ? `/catalogo/admin/variantes/${x.variant_id}/composicion` : `/catalogo/admin/variantes/${x.variant_id}/requerimientos?cantidad=${x.quantity}`; const data=await api(path); $("#composition-result").innerHTML=table(Array.isArray(data) ? data : data.requerimientos,[{key:"articulo",label:"Material",region:"Composición"},{key:"cantidad_estandar",label:"Por unidad",format:UiPresentation.quantity},{key:"cantidad_requerida",label:"Requerido",format:UiPresentation.quantity},{key:"existencia_actual",label:"Existencia",format:UiPresentation.quantity},{key:"faltante",label:"Faltante",format:UiPresentation.quantity},{key:"costo_estimado",label:"Costo estimado",format:formatCurrency}],"No hay materiales configurados."); } catch(error){ notice(error.message,true); } });
  $("#price-scale")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/catalogo/admin/variantes/${x.variant_id}/escalas`, { method:"POST", body:JSON.stringify({ minimum_quantity:+x.minimum_quantity, maximum_quantity:x.maximum_quantity ? +x.maximum_quantity : null, wholesale_unit_price:x.wholesale_unit_price }) }); notice("Escala creada con número automático"); event.target.reset(); } catch(error){ notice(error.message,true); } });
  $("#scale-query")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { const scales=await api(`/catalogo/admin/variantes/${x.variant_id}/escalas`); $("#scale-result").innerHTML=`${table(scales,[{key:"numero_rango",label:"Rango",region:"Escalas mayoristas"},{key:"cantidad_minima",label:"Mínimo"},{key:"cantidad_maxima",label:"Máximo"},{key:"precio_unitario_mayorista",label:"Precio unitario",format:formatCurrency},{key:"estado",label:"Estado",format:UiPresentation.label}],"No hay escalas para esta variante.")}${scales.length ? `<form id="scale-edit" class="form-grid result"><input type="hidden" name="variant_id" value="${x.variant_id}"><label>Rango<select name="range_number">${scales.map((row) => `<option value="${row.numero_rango}" data-min="${row.cantidad_minima}" data-max="${row.cantidad_maxima ?? ""}" data-price="${row.precio_unitario_mayorista}" data-state="${row.estado}">#${row.numero_rango}</option>`).join("")}</select></label><label>Mínimo<input name="minimum_quantity" type="number" min="1" required></label><label>Máximo<input name="maximum_quantity" type="number" min="1"></label><label>Precio<input name="wholesale_unit_price" type="number" min="0" step=".01" required></label><label>Estado<select name="state"><option>ACTIVA</option><option>INACTIVA</option></select></label><button>Guardar escala</button></form>` : ""}`; const form=$("#scale-edit"); const fill=()=>{ const option=form?.elements.range_number.selectedOptions[0]; if(!option)return; form.elements.minimum_quantity.value=option.dataset.min; form.elements.maximum_quantity.value=option.dataset.max; form.elements.wholesale_unit_price.value=option.dataset.price; form.elements.state.value=option.dataset.state; }; form?.elements.range_number.addEventListener("change",fill); fill(); form?.addEventListener("submit", async (editEvent) => { editEvent.preventDefault(); const data=fields(form); try { await api(`/catalogo/admin/variantes/${data.variant_id}/escalas/${data.range_number}`, { method:"PATCH", body:JSON.stringify({ minimum_quantity:+data.minimum_quantity, maximum_quantity:data.maximum_quantity ? +data.maximum_quantity : null, wholesale_unit_price:data.wholesale_unit_price, state:data.state }) }); notice("Escala actualizada"); event.target.requestSubmit(); } catch(error){ notice(error.message,true); } }); } catch(error){ notice(error.message,true); } });
}

async function payments() {
  if (scope === "cliente") {
    const [orders,paymentRows]=await Promise.all([api("/portal/pedidos"),api("/portal/pagos")]);
    const details=await Promise.all(orders.map((order)=>api(`/portal/pedidos/${encodeURIComponent(order.codigo)}`)));
    const payable=details.flatMap((order)=>order.hitos_pago.filter((hito)=>hito.puede_reportar).map((hito)=>({ ...hito, pedido:order.codigo })));
    const balances=orders.length ? `<div class="balance-list">${orders.map((order)=>`<article><span>${escapeHtml(order.codigo)}</span><strong>${escapeHtml(formatCurrency(order.saldo_pendiente))}</strong><small>Saldo pendiente</small></article>`).join("")}</div>` : '<div class="empty-state"><p>Todavía no tienes pedidos con pagos.</p></div>';
    const history=paymentRows.length ? `<div class="payment-list">${paymentRows.map((payment)=>`<article><div><strong>${escapeHtml(payment.pedido)}</strong><span>${escapeHtml(UiPresentation.date(payment.fecha,true))}</span></div><div><strong>${escapeHtml(formatCurrency(payment.monto))}</strong><span>${escapeHtml(UiPresentation.label(payment.estado))} · ${escapeHtml(UiPresentation.label(payment.metodo))}</span></div></article>`).join("")}</div>` : '<div class="empty-state"><p>Aún no has reportado pagos.</p></div>';
    const form=payable.length ? `<article class="panel payment-report"><h2>Reportar un pago</h2><p>El monto se determina en el servidor según el hito seleccionado.</p><form id="report-payment" class="form-grid"><label>Pago pendiente<select name="payable">${payable.map((item)=>`<option value="${escapeHtml(item.pedido)}:${item.numero}">${escapeHtml(item.pedido)} · ${escapeHtml(UiPresentation.label(item.tipo))} · ${escapeHtml(formatCurrency(item.saldo))}</option>`).join("")}</select></label><label>Método<select name="method"><option value="TRANSFERENCIA">Transferencia</option><option value="EFECTIVO">Efectivo</option><option value="TARJETA">Tarjeta</option><option value="OTRO">Otro</option></select></label><label>Referencia opcional<input name="reference"></label><button>Reportar para revisión</button></form></article>` : '<div class="empty-state"><h2>No tienes pagos pendientes</h2><p>Cuando un pedido requiera un pago aparecerá aquí.</p></div>';
    setContent("Pagos", `<div class="section-heading"><div><p class="section-kicker">Tus compromisos</p><h2>Saldos por pedido</h2></div></div>${balances}<div class="two-columns result">${form}<section><h2>Pagos reportados</h2>${history}</section></div>`);
    $("#report-payment")?.addEventListener("submit", async(event)=>{event.preventDefault();const data=fields(event.target);const separator=data.payable.lastIndexOf(":");const code=data.payable.slice(0,separator);const milestone=+data.payable.slice(separator+1);try{await api(`/portal/pedidos/${encodeURIComponent(code)}/pagos`,{method:"POST",body:JSON.stringify({milestone_number:milestone,idempotency_key:crypto.randomUUID(),method:data.method,bank:null,reference:data.reference||null})});notice("Pago reportado. Lo revisaremos antes de actualizar tu saldo.");await payments();}catch(error){notice(error.message,true);}});
    return;
  }
  const rows = await api("/pagos");
  let actions = "";
  if (permitted("PAGO_VERIFICAR") && rows.some((x) => x.estado_verificacion === "PENDIENTE")) actions = `<article class="panel result"><h2>Resolver pago</h2><form id="payment-action" class="form-grid inline"><label>Pago<select name="id">${rows.filter((x) => x.estado_verificacion === "PENDIENTE").map((x) => `<option value="${x.id_transaccion}">#${x.id_transaccion} · pedido ${x.id_pedido} · C$ ${escapeHtml(x.monto_con_signo)}</option>`).join("")}</select></label><label>Decisión<select name="action"><option value="confirmar">Confirmar</option><option value="rechazar">Rechazar</option></select></label><label>Motivo<input name="reason" value="Revisión manual"></label><button>Guardar</button></form></article>`;
  setContent("Pagos", table(rows,columns.payments,"No hay pagos registrados.") + actions);
  $("#payment-action")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/pagos/${x.id}/${x.action}`, { method:"POST", body:x.action === "rechazar" ? JSON.stringify({ reason:x.reason }) : undefined }); notice("Pago resuelto"); await payments(); } catch(error){ notice(error.message,true); } });
}

async function inventory() {
  const [rows, movements] = await Promise.all([api("/inventario/articulos"), api("/inventario/movimientos")]);
  let forms = "";
  if (permitted("INVENTARIO_GESTIONAR")) forms = `<div class="two-columns result"><article class="panel"><h2>Nuevo artículo</h2><form id="new-article" class="form-grid"><label>Código<input name="code" required></label><label>Nombre<input name="name" required></label><label>Tipo<input name="article_type" value="INSUMO" required></label><label>Unidad<select name="unit"><option>UNIDAD</option><option>ML</option><option>L</option><option>G</option><option>KG</option><option>M</option><option>M2</option><option>HOJA</option></select></label><label>Existencia mínima<input name="minimum_stock" type="number" min="0" step=".001" required></label><label>Costo referencia<input name="reference_cost" type="number" min="0" step=".0001" required></label><button>Crear con existencia cero</button></form></article><article class="panel"><h2>Ajuste autorizado</h2><form id="inventory-adjustment" class="form-grid"><label>Artículo<select name="article_id">${options(rows.filter((x) => x.estado === "ACTIVO"),"id_articulo","nombre")}</select></label><label>Dirección<select name="direction"><option>ENTRADA</option><option>SALIDA</option></select></label><label>Cantidad<input name="quantity" type="number" min=".001" step=".001" required></label><label>Motivo<input name="reason" required></label><button>Registrar movimiento</button></form></article><article class="panel"><h2>Activar o desactivar</h2><form id="article-state" class="form-grid"><label>Artículo<select name="operation">${rows.map((x) => `<option value="${x.id_articulo}:${x.estado === "ACTIVO" ? "INACTIVO" : "ACTIVO"}">${escapeHtml(x.nombre)} · ${x.estado === "ACTIVO" ? "desactivar" : "activar"}</option>`).join("")}</select></label><button>Aplicar</button></form></article></div>`;
  setContent("Inventario", table(rows,columns.inventory,"No hay artículos de inventario.") + forms + `<h2>Movimientos recientes</h2>${table(movements,columns.movements,"No hay movimientos recientes.")}`);
  $("#new-article")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/inventario/articulos", { method:"POST", body:JSON.stringify({ code:x.code, name:x.name, article_type:x.article_type, unit:x.unit, minimum_stock:x.minimum_stock, reference_cost:x.reference_cost }) }); notice("Artículo creado con existencia cero"); await inventory(); } catch(error){ notice(error.message,true); } });
  $("#inventory-adjustment")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/inventario/articulos/${x.article_id}/ajustes`, { method:"POST", body:JSON.stringify({ direction:x.direction, quantity:x.quantity, reason:x.reason, observations:null }) }); notice("Ajuste auditado"); await inventory(); } catch(error){ notice(error.message,true); } });
  $("#article-state")?.addEventListener("submit", async (event) => { event.preventDefault(); const [id,state]=fields(event.target).operation.split(":"); try { await api(`/inventario/articulos/${id}`,{ method:"PATCH",body:JSON.stringify({ state }) }); notice("Estado del artículo actualizado"); await inventory(); } catch(error){ notice(error.message,true); } });
}

async function purchases() {
  const [rows, providers, articles] = await Promise.all([api("/compras"), api("/compras/proveedores"), api("/inventario/articulos")]);
  const providerNames = new Map(providers.map((provider) => [provider.id_proveedor, provider.nombre]));
  const presentedRows = rows.map((purchase) => ({ ...purchase, proveedor:providerNames.get(purchase.id_proveedor) || "Proveedor" }));
  let create = "";
  if (permitted("COMPRA_REGISTRAR")) create = `<article class="panel result"><h2>Nueva compra</h2><form id="new-purchase" class="form-grid inline"><label>Proveedor<select name="provider_id">${options(providers,"id_proveedor","nombre")}</select></label><label>Artículo<select name="article_id">${options(articles,"id_articulo","nombre")}</select></label><label>Cantidad<input name="quantity" type="number" min=".001" step=".001" required></label><label>Costo unitario<input name="unit_cost" type="number" min="0" step=".01" required></label><label>Documento<input name="document_number"></label><button>Crear borrador</button></form></article>`;
  let confirm = "";
  if (permitted("COMPRA_AUTORIZAR") && rows.some((x) => x.estado === "BORRADOR")) confirm = `<article class="panel result"><h2>Autorizar entrada</h2><form id="confirm-purchase" class="form-grid inline"><label>Compra revisada<select name="id">${rows.filter((x) => x.estado === "BORRADOR").map((x) => `<option value="${x.id_compra}">#${x.id_compra} · C$ ${escapeHtml(x.total_compra)}</option>`).join("")}</select></label><button>Confirmar una vez</button></form></article>`;
  setContent("Compras", table(presentedRows,columns.purchases,"No hay compras registradas.") + create + confirm);
  $("#new-purchase")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/compras", { method:"POST", body:JSON.stringify({ provider_id:+x.provider_id, document_number:x.document_number || null, lines:[{ article_id:+x.article_id, quantity:x.quantity, unit_cost:x.unit_cost }] }) }); notice("Compra creada en borrador"); await purchases(); } catch(error){ notice(error.message,true); } });
  $("#confirm-purchase")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/compras/${x.id}/confirmar`, { method:"POST" }); notice("Compra confirmada e inventario actualizado"); await purchases(); } catch(error){ notice(error.message,true); } });
}

async function providers() {
  const rows = await api("/compras/proveedores");
  const form = permitted("PROVEEDOR_GESTIONAR") ? `<article class="panel result"><h2>Nuevo proveedor</h2><form id="new-provider" class="form-grid inline"><label>Nombre<input name="name" required></label><label>Correo<input name="email" type="email"></label><label>Teléfono<input name="phone" type="tel"></label><label>Dirección<input name="address"></label><button>Registrar</button></form></article>` : "";
  setContent("Proveedores", table(rows,columns.providers,"No hay proveedores registrados.") + form);
  $("#new-provider")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/compras/proveedores", { method:"POST", body:JSON.stringify({ name:x.name, email:x.email || null, phone:x.phone || null, address:x.address || null }) }); notice("Proveedor registrado"); await providers(); } catch(error){ notice(error.message,true); } });
}

async function losses() {
  const rows = await api("/perdidas");
  let form = "";
  if (permitted("PERDIDA_REGISTRAR")) { const [articles,lossOptions,orders]=await Promise.all([api("/inventario/articulos"),api("/perdidas/opciones"),api("/pedidos")]); form=`<article class="panel result"><h2>Reportar pérdida operativa</h2><form id="new-loss" class="form-grid"><label>Momento<select name="moment">${lossOptions.momentos.map((x)=>`<option value="${x.codigo}">${escapeHtml(x.nombre)}</option>`).join("")}</select></label><label>Tipo de incidente<select name="incident_type">${lossOptions.tipos.map((x)=>`<option value="${x.codigo}">${escapeHtml(x.nombre)}</option>`).join("")}</select></label><label>Pedido relacionado<select name="order_id"><option value="">Sin pedido</option>${orders.map((x)=>`<option value="${x.id_pedido}">${escapeHtml(x.codigo_pedido)} · ${escapeHtml(x.estado)}</option>`).join("")}</select></label><label>Etapa<select name="stage_id"><option value="">Sin etapa</option>${lossOptions.etapas.map((x)=>`<option value="${x.id_etapa}">${escapeHtml(x.nombre)}</option>`).join("")}</select></label><label>Artículo<select name="article_id">${options(articles,"id_articulo","nombre")}</select></label><label>Cantidad<input name="quantity" type="number" min=".001" step=".001" required></label><label>Motivo<input name="reason" required></label><label>Descripción del incidente<textarea name="description"></textarea></label><label>Daño del material<textarea name="damage_description"></textarea></label><button>Reportar y confirmar</button></form></article>`; }
  setContent(scope === "produccion" ? "Incidencias operativas" : "Pérdidas", table(rows,columns.losses,scope === "produccion" ? "No hay incidencias de producción." : "No hay pérdidas registradas.") + form);
  const lossForm=$("#new-loss"); const updateLossContext=()=>{ if(!lossForm)return; const outside=lossForm.elements.moment.value==="FUERA_PRODUCCION"; lossForm.elements.stage_id.disabled=outside; if(outside) lossForm.elements.stage_id.value=""; }; lossForm?.elements.moment.addEventListener("change",updateLossContext); updateLossContext();
  lossForm?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { const loss=await api("/perdidas", { method:"POST", body:JSON.stringify({ moment:x.moment, incident_type:x.incident_type, reason:x.reason, order_id:x.order_id ? +x.order_id : null, stage_id:x.stage_id ? +x.stage_id : null, description:x.description || null }) }); await api(`/perdidas/${loss.id_perdida}/confirmar`, { method:"POST", body:JSON.stringify({ lines:[{ article_id:+x.article_id, quantity:x.quantity, damage_description:x.damage_description || null }] }) }); notice("Pérdida confirmada y movimiento de inventario registrado"); await losses(); } catch(error){ notice(error.message,true); } });
}

async function reports() { const report=await api("/reportes/resumen?days=30"); setContent("Reportes financieros", `<div class="metrics"><article class="metric"><span>Ingresos verificados</span><strong>${escapeHtml(formatCurrency(report.ingresos_verificados))}</strong></article><article class="metric"><span>Compras confirmadas</span><strong>${escapeHtml(formatCurrency(report.compras_confirmadas.total))}</strong></article><article class="metric"><span>Pagos pendientes</span><strong>${escapeHtml(formatCurrency(report.pagos_pendientes.monto))}</strong></article></div><h2>Pedidos por estado</h2>${table(report.pedidos_por_estado,[{key:"estado",label:"Estado",region:"Pedidos por estado",format:UiPresentation.label},{key:"cantidad",label:"Cantidad"}],"No hay pedidos en el periodo.")}<h2>Compras por proveedor</h2>${table(report.compras_por_proveedor,[{key:"nombre",label:"Proveedor",region:"Compras por proveedor"},{key:"articulos_comprados",label:"Artículos",format:UiPresentation.quantity},{key:"total_documentado",label:"Total",format:formatCurrency}],"No hay compras confirmadas.")}<h2>Stock bajo</h2>${table(report.stock_bajo,[{key:"codigo",label:"Código",region:"Stock bajo"},{key:"nombre",label:"Artículo"},{key:"disponible",label:"Disponible",format:UiPresentation.quantity},{key:"existencia_minima",label:"Mínimo",format:UiPresentation.quantity}],"No hay artículos con stock bajo.")}<h2>Pérdidas principales</h2>${table(report.perdidas_principales,[{key:"nombre",label:"Artículo",region:"Pérdidas principales"},{key:"cantidad_perdida",label:"Cantidad",format:UiPresentation.quantity},{key:"costo_perdida",label:"Costo",format:formatCurrency}],"No hay pérdidas en el periodo.")}<h2>Actividad reciente</h2>${table(report.actividad_reciente,[{key:"fecha_hora",label:"Fecha",region:"Actividad reciente",format:(value)=>UiPresentation.date(value,true)},{key:"accion",label:"Acción",format:UiPresentation.label},{key:"tipo_objeto_afectado",label:"Área",format:UiPresentation.label},{key:"referencia_objeto",label:"Referencia"}],"No hay actividad reciente.")}`); }
async function clients() { const rows=await api("/clientes"); if(!rows.length){setContent("Clientes",'<div class="empty-state"><h2>No hay clientes registrados</h2><p>Los clientes aparecerán aquí al crear su cuenta o realizar una operación autorizada.</p></div>');return;} setContent("Clientes",`<article class="panel"><h2>Directorio de clientes</h2><label>Selecciona un cliente<select id="client-selector">${rows.map((x)=>`<option value="${x.id_persona}">${escapeHtml(x.nombre)}</option>`).join("")}</select></label></article><div id="client-detail" class="result"></div>`); const load=async()=>{ const id=$("#client-selector").value; const client=await api(`/clientes/${id}`); $("#client-detail").innerHTML=clientDetailHtml(client); $("#edit-client")?.addEventListener("submit",async(event)=>{event.preventDefault();const x=fields(event.target);try{await api(`/clientes/${id}`,{method:"PATCH",body:JSON.stringify({names:x.names,surnames:x.surnames||null,phone:x.phone||null,document:x.document||null,usual_address:x.usual_address||null})});notice("Ficha del cliente actualizada");await load();}catch(error){notice(error.message,true);}}); $("#wholesale-client")?.addEventListener("submit",async(event)=>{event.preventDefault();const x=fields(event.target);if(!confirm(x.enabled==="true"?"¿Autorizar la condición mayorista?":"¿Revocar la condición mayorista?"))return;try{await api(`/clientes/${id}/condicion-mayorista`,{method:"POST",body:JSON.stringify({enabled:x.enabled==="true",reason:x.reason})});notice("Condición comercial registrada");await load();}catch(error){notice(error.message,true);}}); }; $("#client-selector").addEventListener("change",()=>load().catch((error)=>notice(error.message,true))); await load(); }

async function tracking() {
  if (scope === "cliente") {
    const rows=await api("/portal/pedidos");
    if (!rows.length) { setContent("Seguimiento",'<div class="empty-state customer-empty"><h2>Todavía no tienes pedidos</h2><p>Cuando hagas tu primer pedido podrás seguir cada etapa aquí.</p></div>'); return; }
    setContent("Seguimiento", `<article class="panel track-selector"><form id="track-order" class="form-grid inline"><label>Pedido<select name="code">${rows.map((order)=>`<option value="${escapeHtml(order.codigo)}">${escapeHtml(order.codigo)} · ${escapeHtml(UiPresentation.label(order.estado))}</option>`).join("")}</select></label><button>Ver progreso</button></form></article><div id="tracking-result" class="result"></div>`);
    const load=async()=>{const order=await api(`/portal/pedidos/${encodeURIComponent($("#track-order").elements.code.value)}`);$("#tracking-result").innerHTML=`<article class="tracking-card"><header><div><p class="section-kicker">${escapeHtml(UiPresentation.orderMessage(order.estado))}</p><h2>${escapeHtml(order.codigo)}</h2></div><span class="status">${escapeHtml(UiPresentation.label(order.estado))}</span></header>${orderProgress(order)}<p><strong>Próxima acción:</strong> ${escapeHtml(UiPresentation.label(order.proxima_accion))}</p></article>`;};
    $("#track-order").addEventListener("submit",(event)=>{event.preventDefault();load().catch((error)=>notice(error.message,true));});
    await load(); return;
  }
  const rows=await api("/pedidos");
  setContent("Seguimiento", table(rows,columns.orders,"No hay pedidos para seguimiento."));
}

async function employees() {
  const [rows, roles] = await Promise.all([api("/empleados"), api("/empleados/roles")]);
  const roleOptions = options(roles,"id_rol","nombre");
  setContent("Empleados y roles", `${employeeTable(rows)}<p class="muted result">“Solicitud aceptada” confirma que Supabase recibió la petición. La entrega del correo depende del proveedor. Si la redirección usa 127.0.0.1, el enlace sólo abre en la computadora que aloja FastAPI.</p><div class="two-columns result"><article class="panel"><h2>Invitar empleado</h2><form id="invite-employee" class="form-grid"><label>Nombres<input name="names" required></label><label>Apellidos<input name="surnames"></label><label>Correo<input name="email" type="email" required></label><label>Teléfono<input name="phone" type="tel"></label><label>Documento<input name="document"></label><label>Rol<select name="role_id">${roleOptions}</select></label><button>Solicitar invitación segura</button></form></article><article class="panel"><h2>Cambiar rol</h2><form id="assign-role" class="form-grid"><label>Empleado<select name="employee_id">${rows.map((x) => `<option value="${x.id_persona}">${escapeHtml(x.nombre)} · ${escapeHtml(x.codigo_empleado)}</option>`).join("")}</select></label><label>Rol<select name="role_id">${roleOptions}</select></label><button>Asignar</button></form></article></div>`);
  $("#invite-employee").addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/empleados/invitaciones", { method:"POST", body:JSON.stringify({ ...x, role_id:+x.role_id, capacity:10, surnames:x.surnames || null, phone:x.phone || null, document:x.document || null }) }); notice("Supabase aceptó la solicitud; la activación y entrega del correo siguen pendientes"); await employees(); } catch(error){ notice(error.message,true); } });
  $("#assign-role").addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/empleados/${x.employee_id}/rol`, { method:"PUT", body:JSON.stringify({ role_id:+x.role_id }) }); notice("Rol actualizado; será efectivo en la próxima consulta"); await employees(); } catch(error){ notice(error.message,true); } });
  document.querySelectorAll(".resend-invitation").forEach((button) => button.addEventListener("click", async () => { button.disabled=true; try { await api(`/empleados/${button.dataset.employeeId}/reenviar-invitacion`, { method:"POST" }); notice("Supabase aceptó la solicitud de un enlace nuevo; la entrega sigue pendiente"); await employees(); } catch(error) { notice(error.message,true); button.disabled=false; } }));
}

async function designs() {
  const rows = await api("/pedidos");
  const summaries = await Promise.all(rows.map((x) => api(`/pedidos/${x.id_pedido}/operacion`)));
  const orderOptions=rows.map((x) => `<option value="${x.id_pedido}">${escapeHtml(x.codigo_pedido)} · ${escapeHtml(x.estado)}</option>`).join("");
  const actionMap = { INICIAR_PRODUCCION:["start","Iniciar producción"], CONSUMIR_RESERVAS:["consume","Consumir reservas"], COMPLETAR_PRODUCCION:["finish","Completar producción"] };
  const available = summaries.flatMap((summary) => summary.produccion.acciones_permitidas.filter((code) => permitted(productionPermissions[code])).map((code) => ({ id:summary.pedido.id_pedido, pedido:summary.pedido.codigo_pedido, code, action:actionMap[code][0], label:actionMap[code][1] })));
  const productionPanel = available.length ? `<article class="panel"><h2>Operación de producción</h2><form id="production-action" class="form-grid"><label>Acción permitida<select name="operation">${available.map((x) => `<option value="${x.id}:${x.action}">${escapeHtml(x.pedido)} · ${escapeHtml(x.label)}</option>`).join("")}</select></label><button>Ejecutar</button></form></article>` : '<article class="panel"><h2>Operación de producción</h2><p class="muted">No hay acciones de producción autorizadas en este momento.</p></article>';
  const operationalState = table(summaries.map((x) => ({ pedido:x.pedido.codigo_pedido, estado:x.pedido.estado, diseno:x.disenos.every((item)=>!item.requiere_produccion||item.aprobada) ? "APROBADO" : "PENDIENTE", materiales:x.inventario.reservas.length, siguiente:x.siguiente_accion, condicion:x.produccion.mensaje })),[{key:"pedido",label:"Pedido",region:"Trabajo de producción"},{key:"estado",label:"Estado",format:UiPresentation.label},{key:"diseno",label:"Diseño",format:UiPresentation.label},{key:"materiales",label:"Reservas"},{key:"siguiente",label:"Próxima acción",format:UiPresentation.label},{key:"condicion",label:"Condición"}],"No hay pedidos esperando producción.");
  setContent("Diseños", `<div class="two-columns result"><article class="panel"><h2>Nueva versión privada</h2><form id="upload-design" class="form-grid"><label>Pedido<select name="order_id">${orderOptions}</select></label><label>Línea<input name="line" type="number" min="1" value="1" required></label><label>Archivo<input name="file" type="file" accept="image/png,image/jpeg,application/pdf" required></label><button>Subir</button></form></article><article class="panel"><h2>Revisar versiones</h2><form id="load-designs" class="form-grid"><label>Pedido<select name="order_id">${orderOptions}</select></label><label>Línea<input name="line" type="number" min="1" value="1" required></label><button>Consultar versiones</button></form></article>${productionPanel}</div><h2>Pedidos disponibles</h2>${table(rows,columns.orders,"No hay pedidos asignados a esta vista.")}<h2>Estado operativo</h2>${operationalState}<div id="design-versions" class="result"></div>`);
  $("#upload-design").addEventListener("submit", async (event) => { event.preventDefault(); const x=new FormData(event.target); const order=x.get("order_id"), line=x.get("line"); x.delete("order_id"); x.delete("line"); try { await api(`/disenos/pedidos/${order}/lineas/${line}/versiones`, { method:"POST", body:x }); notice("Versión de diseño almacenada"); } catch(error){ notice(error.message,true); } });
  $("#load-designs").addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { const versions=await api(`/disenos/pedidos/${x.order_id}/lineas/${x.line}/versiones`); $("#design-versions").innerHTML=`${table(versions,[{key:"numero_version",label:"Versión",region:"Versiones de diseño"},{key:"nombre_archivo",label:"Archivo"},{key:"fecha_creacion",label:"Fecha",format:(value)=>UiPresentation.date(value,true)},{key:"es_aprobado",label:"Decisión",format:(value)=>value?"Aprobado":"Pendiente"}],"No hay versiones para esta línea.")}${versions.length ? `<article class="panel result"><form id="design-decision" class="form-grid inline"><input type="hidden" name="order_id" value="${x.order_id}"><input type="hidden" name="line" value="${x.line}"><label>Versión<select name="version">${versions.map((v) => `<option value="${v.numero_version}">Versión ${v.numero_version} · ${escapeHtml(v.nombre_archivo)}</option>`).join("")}</select></label><label>Decisión<select name="approved"><option value="true">Aprobar</option><option value="false">Rechazar</option></select></label><button>Registrar decisión</button></form></article>` : ""}`; $("#design-decision")?.addEventListener("submit", async (decisionEvent) => { decisionEvent.preventDefault(); const d=fields(decisionEvent.target); if(!confirm(d.approved==="true"?"¿Aprobar esta versión de diseño?":"¿Rechazar esta versión de diseño?"))return; try { await api(`/disenos/pedidos/${d.order_id}/lineas/${d.line}/versiones/${d.version}/decision`, { method:"POST", body:JSON.stringify({ approved:d.approved === "true", medium:"PORTAL" }) }); notice("Decisión de diseño registrada"); } catch(error){ notice(error.message,true); } }); } catch(error){ notice(error.message,true); } });
  $("#production-action")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); const [orderId,action]=x.operation.split(":"); const paths={ start:`/produccion/pedidos/${orderId}/iniciar`, consume:`/inventario/pedidos/${orderId}/consumir`, finish:`/produccion/pedidos/${orderId}/completar` }; try { await api(paths[action],{ method:"POST" }); notice("Operación de producción completada"); await designs(); } catch(error){ notice(error.message,true); } });
}
async function profile() { const data=await api("/perfil"); setContent("Mi perfil",`<div class="two-columns"><article class="panel"><h2>Datos personales</h2><form id="profile-form" class="form-grid"><label>Nombres<input name="names" value="${escapeHtml(data.nombres)}" required></label><label>Apellidos<input name="surnames" value="${escapeHtml(data.apellidos)}"></label><label>Teléfono<input name="phone" type="tel" value="${escapeHtml(data.telefono)}"></label><label>Documento<input name="document" value="${escapeHtml(data.documento)}"></label><label>Dirección habitual<textarea name="usual_address">${escapeHtml(data.direccion_habitual)}</textarea></label><button>Guardar mis datos</button></form></article><article class="panel"><h2>Seguridad e identidad</h2><dl><dt>Correo verificado</dt><dd>${escapeHtml(data.correo)}</dd><dt>Perfil</dt><dd>${escapeHtml(data.tipo_perfil)}</dd><dt>Roles</dt><dd>${escapeHtml(data.roles.join(", ") || "Cliente")}</dd><dt>Condición comercial</dt><dd>${escapeHtml(data.condicion_comercial || "No aplica")}</dd></dl><form id="email-change" class="form-grid"><label>Nuevo correo<input name="new_email" type="email" required></label><button>Solicitar cambio verificado</button></form><button id="sync-email" type="button" class="secondary result">Sincronizar correo ya confirmado</button><p class="muted">Los roles, permisos, identidad de acceso y condición mayorista sólo pueden cambiarse mediante operaciones administrativas autorizadas.</p></article></div>`); $("#profile-form").addEventListener("submit",async(event)=>{event.preventDefault();const x=fields(event.target);try{await api("/perfil",{method:"PATCH",body:JSON.stringify({names:x.names,surnames:x.surnames||null,phone:x.phone||null,document:x.document||null,usual_address:x.usual_address||null})});notice("Perfil actualizado");await profile();}catch(error){notice(error.message,true);}}); $("#email-change").addEventListener("submit",async(event)=>{event.preventDefault();const x=fields(event.target);try{await api("/perfil/correo/solicitar",{method:"POST",body:JSON.stringify({new_email:x.new_email})});notice("Supabase aceptó la solicitud. Confirma el nuevo correo y vuelve a iniciar sesión.");}catch(error){notice(error.message,true);}}); $("#sync-email").addEventListener("click",async()=>{try{await api("/perfil/correo/sincronizar",{method:"POST"});notice("Correo verificado sincronizado");await profile();}catch(error){notice(error.message,true);}}); }

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
  try {
    identity = await AuthSession.verifyIdentity(
      () => api("/auth/me"),
      { retries: 2, sleep: (delay) => new Promise((resolve) => setTimeout(resolve, delay)) },
    );
  } catch (error) {
    const outcome = AuthSession.classifyIdentityError(error);
    if (outcome.clearSession) {
      sessionStorage.removeItem("s2r_access_token");
      location.assign("/app/#acceso");
      return;
    }
    notice(outcome.message, true);
    return;
  }
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
