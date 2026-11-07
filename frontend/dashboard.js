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
  return AuthSession.requestJSON(fetch, `/api/v1${path}`, { ...options, headers });
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
  admin: [["summary","Resumen"],["orders","Pedidos","PEDIDO_GESTIONAR"],["quotes","Cotizaciones","PEDIDO_GESTIONAR"],["clients","Clientes","PEDIDO_GESTIONAR"],["catalog","Catálogo y recetas","CATALOGO_GESTIONAR"],["inventory","Inventario","INVENTARIO_CONSULTAR"],["purchases","Compras","COMPRA_CONSULTAR"],["providers","Proveedores","PROVEEDOR_CONSULTAR"],["payments","Pagos","PAGO_CONSULTAR"],["losses","Pérdidas","PERDIDA_CONSULTAR"],["reports","Reportes","REPORTE_FINANCIERO_CONSULTAR"],["employees","Empleados y roles","EMPLEADO_GESTIONAR"],["profile","Mi perfil"]],
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
    setContent("Resumen", `<div class="metrics"><article class="metric"><span>Ingreso verificado · ${report.periodo_dias} días</span><strong>C$ ${escapeHtml(report.ingresos_verificados)}</strong></article><article class="metric"><span>Pagos por revisar</span><strong>${escapeHtml(report.pagos_pendientes.cantidad)}</strong></article><article class="metric"><span>Compras confirmadas</span><strong>${escapeHtml(report.compras_confirmadas.cantidad)}</strong></article><article class="metric"><span>Stock bajo</span><strong>${report.stock_bajo.length}</strong></article></div><h2>Pedidos por estado</h2>${table(report.pedidos_por_estado)}<h2>Actividad reciente</h2>${table(report.actividad_reciente)}<h2>Productos más vendidos</h2>${table(report.productos_mas_vendidos)}`);
  } else {
    const orders = await api("/pedidos");
    setContent("Trabajo pendiente", `<div class="metrics"><article class="metric"><span>Pedidos visibles</span><strong>${orders.length}</strong></article><article class="metric"><span>En producción</span><strong>${orders.filter((x) => x.estado === "EN_PRODUCCION").length}</strong></article></div>${table(orders)}`);
  }
}

async function orders() {
  const rows = await api("/pedidos");
  const orderOptions = rows.map((x) => `<option value="${x.id_pedido}">${escapeHtml(x.codigo_pedido)} · ${escapeHtml(x.estado)}</option>`).join("");
  let forms = "";
  if (permitted("PEDIDO_GESTIONAR") && rows.length) {
    const productionActions = permitted("PRODUCCION_INICIAR") ? '<option value="start">Iniciar producción</option><option value="consume">Consumir reservas</option><option value="finish">Completar producción</option>' : "";
    forms = `<div class="two-columns result"><article class="panel"><h2>Operación segura</h2><form id="order-operation" class="form-grid"><label>Pedido<select name="id">${orderOptions}</select></label><label>Acción<select name="action"><option value="design">Iniciar diseño</option>${productionActions}<option value="deliver">Completar entrega o retiro</option></select></label><label>Motivo<input name="reason" value="Operación verificada desde el panel" required></label><button>Ejecutar</button></form></article><article class="panel"><h2>Estado integral</h2><form id="order-summary" class="form-grid"><label>Pedido<select name="id">${orderOptions}</select></label><button>Consultar siguiente acción</button></form><div id="order-summary-result" class="result"></div></article><article class="panel"><h2>Programar envío</h2><form id="delivery-schedule" class="form-grid"><label>Pedido<select name="id">${orderOptions}</select></label><label>Dirección<input name="address" required></label><label>Persona receptora<input name="recipient_name" required></label><label>Teléfono<input name="recipient_phone"></label><button>Programar</button></form></article></div>`;
  }
  setContent(scope === "cliente" ? "Mis pedidos" : "Pedidos", table(rows) + forms);
  $("#order-operation")?.addEventListener("submit", async (event) => {
    event.preventDefault(); const x = fields(event.target);
    const actions = {
      design: [`/pedidos/${x.id}/estado`, { target:"EN_DISENO", reason:x.reason }],
      start: [`/produccion/pedidos/${x.id}/iniciar`, null],
      consume: [`/inventario/pedidos/${x.id}/consumir`, null],
      finish: [`/produccion/pedidos/${x.id}/completar`, null],
      deliver: [`/entregas/pedidos/${x.id}/completar`, { reason:x.reason }],
    };
    try { const [path, payload] = actions[x.action]; await api(path, { method:"POST", body:payload ? JSON.stringify(payload) : undefined }); notice("Operación registrada"); await orders(); } catch(error) { notice(error.message,true); }
  });
  $("#order-summary")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { const data=await api(`/pedidos/${x.id}/operacion`); $("#order-summary-result").innerHTML=`<p><strong>Siguiente acción:</strong> ${escapeHtml(data.siguiente_accion)}</p>${table(data.pago.hitos)}${table(data.inventario.reservas)}`; } catch(error){ notice(error.message,true); } });
  $("#delivery-schedule")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/entregas/pedidos/${x.id}`, { method:"POST", body:JSON.stringify({ agency_id:null, address:x.address, recipient_name:x.recipient_name, recipient_phone:x.recipient_phone || null, agreed_fee:"0.00", scheduled_at:null }) }); notice("Envío programado"); } catch(error){ notice(error.message,true); } });
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
  if (permitted("CATALOGO_GESTIONAR")) {
    const [categories, products, adminVariants, articles] = await Promise.all([api("/catalogo/admin/categorias"), api("/catalogo/admin/productos"), api("/catalogo/admin/variantes"), api("/inventario/articulos")]);
    const categoryOptions = options(categories.filter((x) => x.estado === "ACTIVA"), "id_categoria", "nombre");
    const productOptions = options(products, "id_producto", "nombre");
    const variantOptions = adminVariants.map((x) => `<option value="${x.id_variante}">${escapeHtml(x.codigo_variante)}</option>`).join("");
    forms = `<h2>Mantenimiento</h2><div class="two-columns result"><article class="panel"><h3>Nueva categoría</h3><form id="new-category" class="form-grid"><label>Nombre<input name="name" required></label><label>Descripción<input name="description"></label><button>Crear categoría</button></form></article><article class="panel"><h3>Nuevo producto</h3><form id="new-product" class="form-grid"><label>Categoría<select name="category_id">${categoryOptions}</select></label><label>Nombre<input name="name" required></label><label>Información comercial<textarea name="commercial_information" required></textarea></label><button>Crear borrador</button></form></article><article class="panel"><h3>Nueva variante</h3><form id="new-variant" class="form-grid"><label>Producto<select name="product_id">${productOptions}</select></label><label>Código<input name="code" required></label><label>Precio detalle<input name="retail_price" type="number" min="0" step=".01" required></label><label><input name="requires_production" type="checkbox" checked> Requiere producción</label><button>Crear variante</button></form></article><article class="panel"><h3>Composición</h3><form id="composition" class="form-grid"><label>Variante<select name="variant_id">${variantOptions}</select></label><label>Artículo<select name="article_id">${options(articles.filter((x) => x.estado === "ACTIVO"),"id_articulo","nombre")}</select></label><label>Cantidad estándar<input name="standard_quantity" type="number" min=".001" step=".001" required></label><label>Observación<input name="observations"></label><button>Guardar componente</button></form></article><article class="panel"><h3>Escala mayorista</h3><form id="price-scale" class="form-grid"><label>Variante<select name="variant_id">${variantOptions}</select></label><label>Número de rango<input name="range_number" type="number" min="1" required></label><label>Mínimo<input name="minimum_quantity" type="number" min="1" required></label><label>Máximo<input name="maximum_quantity" type="number" min="1"></label><label>Precio unitario<input name="wholesale_unit_price" type="number" min="0" step=".01" required></label><button>Guardar escala</button></form></article></div><h2>Categorías</h2>${table(categories)}<h2>Productos</h2>${table(products)}<h2>Variantes</h2>${table(adminVariants)}`;
  }
  setContent("Catálogo", `<div class="cards">${variants.map((x) => `<article class="product-card"><span>${escapeHtml(x.categoria)}</span><h3>${escapeHtml(x.producto)}</h3><p>${escapeHtml(x.codigo)}</p><strong>C$ ${escapeHtml(x.precio_detalle)}</strong></article>`).join("")}</div>${forms}`);
  $("#new-order")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/pedidos", { method:"POST", body:JSON.stringify({ lines:[{ variant_id:+x.variant_id, quantity:+x.quantity, promotion_id:null }], delivery_mode:x.delivery_mode }) }); notice("Pedido creado"); } catch(error){ notice(error.message,true); } });
  $("#new-quote")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/cotizaciones", { method:"POST", body:JSON.stringify({ lines:[{ variant_id:+x.variant_id, quantity:+x.quantity, customization:x.customization || null }], observations:null }) }); notice("Cotización creada"); } catch(error){ notice(error.message,true); } });
  $("#new-category")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/catalogo/admin/categorias", { method:"POST", body:JSON.stringify({ name:x.name, description:x.description || null }) }); notice("Categoría creada"); await catalog(); } catch(error){ notice(error.message,true); } });
  $("#new-product")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/catalogo/admin/productos", { method:"POST", body:JSON.stringify({ category_id:+x.category_id, name:x.name, description:null, commercial_information:x.commercial_information, publication_state:"BORRADOR" }) }); notice("Producto creado en borrador"); await catalog(); } catch(error){ notice(error.message,true); } });
  $("#new-variant")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/catalogo/admin/variantes", { method:"POST", body:JSON.stringify({ product_id:+x.product_id, code:x.code, features:null, retail_price:x.retail_price, requires_production:event.target.requires_production.checked }) }); notice("Variante creada"); await catalog(); } catch(error){ notice(error.message,true); } });
  $("#composition")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/catalogo/admin/variantes/${x.variant_id}/composicion/${x.article_id}`, { method:"PUT", body:JSON.stringify({ standard_quantity:x.standard_quantity, observations:x.observations || "" }) }); notice("Composición actualizada"); } catch(error){ notice(error.message,true); } });
  $("#price-scale")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/catalogo/admin/variantes/${x.variant_id}/escalas/${x.range_number}`, { method:"PUT", body:JSON.stringify({ range_number:+x.range_number, minimum_quantity:+x.minimum_quantity, maximum_quantity:x.maximum_quantity ? +x.maximum_quantity : null, wholesale_unit_price:x.wholesale_unit_price, state:"ACTIVA" }) }); notice("Escala actualizada"); } catch(error){ notice(error.message,true); } });
}

async function payments() {
  let rows;
  let orderRows = [];
  let summaries = [];
  if (scope === "cliente") {
    orderRows = await api("/pedidos");
    const groups = await Promise.all(orderRows.map((order) => Promise.all([api(`/pagos/pedidos/${order.id_pedido}`), api(`/pagos/pedidos/${order.id_pedido}/resumen`)])));
    rows = groups.flatMap((item) => item[0]);
    summaries = groups.map((item) => item[1]);
  } else rows = await api("/pagos");
  let report = "";
  const payable = summaries.flatMap((summary) => summary.hitos.filter((hito) => hito.puede_reportar).map((hito) => ({ ...hito, id_pedido:summary.id_pedido, codigo_pedido:summary.codigo_pedido })));
  if (scope === "cliente") report = `<h2>Saldos por pedido</h2>${table(summaries.map((x) => ({ codigo_pedido:x.codigo_pedido, total:x.total_pedido, anticipo_verificado:x.anticipo_verificado, pendiente_verificacion:x.anticipo_pendiente_verificacion, saldo_pendiente:x.saldo_pendiente, completamente_pagado:x.completamente_pagado })))}${payable.length ? `<article class="panel result"><h2>Reportar pago exacto</h2><form id="report-payment" class="form-grid inline"><label>Hito disponible<select name="payable">${payable.map((x) => `<option value="${x.id_pedido}:${x.numero_hito}">${escapeHtml(x.codigo_pedido)} · ${escapeHtml(x.tipo_hito)} · C$ ${escapeHtml(x.monto_restante)}</option>`).join("")}</select></label><label>Método<select name="method"><option>TRANSFERENCIA</option><option>EFECTIVO</option><option>TARJETA</option><option>OTRO</option></select></label><label>Referencia<input name="reference"></label><button>Reportar para revisión</button></form></article>` : '<article class="panel result"><p>No hay hitos disponibles para reportar.</p></article>'}`;
  let actions = "";
  if (permitted("PAGO_VERIFICAR") && rows.some((x) => x.estado_verificacion === "PENDIENTE")) actions = `<article class="panel result"><h2>Resolver pago</h2><form id="payment-action" class="form-grid inline"><label>Pago<select name="id">${rows.filter((x) => x.estado_verificacion === "PENDIENTE").map((x) => `<option value="${x.id_transaccion}">#${x.id_transaccion} · pedido ${x.id_pedido} · C$ ${escapeHtml(x.monto_con_signo)}</option>`).join("")}</select></label><label>Decisión<select name="action"><option value="confirmar">Confirmar</option><option value="rechazar">Rechazar</option></select></label><label>Motivo<input name="reason" value="Revisión manual"></label><button>Guardar</button></form></article>`;
  setContent("Pagos", table(rows) + report + actions);
  $("#report-payment")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); const [orderId, milestone]=x.payable.split(":"); try { await api(`/pagos/pedidos/${orderId}/reportar`, { method:"POST", body:JSON.stringify({ milestone_number:+milestone, idempotency_key:crypto.randomUUID(), method:x.method, bank:null, reference:x.reference || null }) }); notice("Pago reportado para revisión"); await payments(); } catch(error){ notice(error.message,true); } });
  $("#payment-action")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/pagos/${x.id}/${x.action}`, { method:"POST", body:x.action === "rechazar" ? JSON.stringify({ reason:x.reason }) : undefined }); notice("Pago resuelto"); await payments(); } catch(error){ notice(error.message,true); } });
}

async function inventory() {
  const rows = await api("/inventario/articulos");
  let forms = "";
  if (permitted("INVENTARIO_GESTIONAR")) forms = `<div class="two-columns result"><article class="panel"><h2>Nuevo artículo</h2><form id="new-article" class="form-grid"><label>Código<input name="code" required></label><label>Nombre<input name="name" required></label><label>Tipo<input name="article_type" value="INSUMO" required></label><label>Unidad<select name="unit"><option>UNIDAD</option><option>ML</option><option>L</option><option>G</option><option>KG</option><option>M</option><option>M2</option><option>HOJA</option></select></label><label>Existencia mínima<input name="minimum_stock" type="number" min="0" step=".001" required></label><label>Costo referencia<input name="reference_cost" type="number" min="0" step=".0001" required></label><button>Crear con existencia cero</button></form></article><article class="panel"><h2>Ajuste autorizado</h2><form id="inventory-adjustment" class="form-grid"><label>Artículo<select name="article_id">${options(rows.filter((x) => x.estado === "ACTIVO"),"id_articulo","nombre")}</select></label><label>Dirección<select name="direction"><option>ENTRADA</option><option>SALIDA</option></select></label><label>Cantidad<input name="quantity" type="number" min=".001" step=".001" required></label><label>Motivo<input name="reason" required></label><button>Registrar movimiento</button></form></article></div>`;
  setContent("Inventario", table(rows) + forms);
  $("#new-article")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api("/inventario/articulos", { method:"POST", body:JSON.stringify({ code:x.code, name:x.name, article_type:x.article_type, unit:x.unit, minimum_stock:x.minimum_stock, reference_cost:x.reference_cost }) }); notice("Artículo creado con existencia cero"); await inventory(); } catch(error){ notice(error.message,true); } });
  $("#inventory-adjustment")?.addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { await api(`/inventario/articulos/${x.article_id}/ajustes`, { method:"POST", body:JSON.stringify({ direction:x.direction, quantity:x.quantity, reason:x.reason, observations:null }) }); notice("Ajuste auditado"); await inventory(); } catch(error){ notice(error.message,true); } });
}

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

async function reports() { const report=await api("/reportes/resumen?days=30"); setContent("Reportes financieros", `<div class="metrics"><article class="metric"><span>Ingresos verificados</span><strong>C$ ${escapeHtml(report.ingresos_verificados)}</strong></article><article class="metric"><span>Compras confirmadas</span><strong>C$ ${escapeHtml(report.compras_confirmadas.total)}</strong></article><article class="metric"><span>Pagos pendientes</span><strong>C$ ${escapeHtml(report.pagos_pendientes.monto)}</strong></article></div><h2>Pedidos por estado</h2>${table(report.pedidos_por_estado)}<h2>Compras por proveedor</h2>${table(report.compras_por_proveedor)}<h2>Stock bajo</h2>${table(report.stock_bajo)}<h2>Pérdidas principales</h2>${table(report.perdidas_principales)}<h2>Actividad reciente</h2>${table(report.actividad_reciente)}`); }
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
  setContent("Diseños", `${table(rows)}<div class="two-columns result"><article class="panel"><h2>Nueva versión privada</h2><form id="upload-design" class="form-grid"><label>Pedido<select name="order_id">${orderOptions}</select></label><label>Línea<input name="line" type="number" min="1" value="1" required></label><label>Archivo<input name="file" type="file" accept="image/png,image/jpeg,application/pdf" required></label><button>Subir</button></form></article><article class="panel"><h2>Revisar versiones</h2><form id="load-designs" class="form-grid"><label>Pedido<select name="order_id">${orderOptions}</select></label><label>Línea<input name="line" type="number" min="1" value="1" required></label><button>Consultar versiones</button></form></article><article class="panel"><h2>Operación de producción</h2><form id="production-action" class="form-grid"><label>Pedido<select name="order_id">${orderOptions}</select></label><label>Operación<select name="action"><option value="start">Iniciar producción</option><option value="consume">Consumir reserva</option><option value="finish">Completar producción</option></select></label><button>Ejecutar</button></form></article></div><div id="design-versions" class="result"></div>`);
  $("#upload-design").addEventListener("submit", async (event) => { event.preventDefault(); const x=new FormData(event.target); const order=x.get("order_id"), line=x.get("line"); x.delete("order_id"); x.delete("line"); try { await api(`/disenos/pedidos/${order}/lineas/${line}/versiones`, { method:"POST", body:x }); notice("Versión de diseño almacenada"); } catch(error){ notice(error.message,true); } });
  $("#load-designs").addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); try { const versions=await api(`/disenos/pedidos/${x.order_id}/lineas/${x.line}/versiones`); $("#design-versions").innerHTML=`${table(versions)}${versions.length ? `<article class="panel result"><form id="design-decision" class="form-grid inline"><input type="hidden" name="order_id" value="${x.order_id}"><input type="hidden" name="line" value="${x.line}"><label>Versión<select name="version">${versions.map((v) => `<option value="${v.numero_version}">Versión ${v.numero_version} · ${escapeHtml(v.nombre_archivo)}</option>`).join("")}</select></label><label>Decisión<select name="approved"><option value="true">Aprobar</option><option value="false">Rechazar</option></select></label><button>Registrar decisión</button></form></article>` : ""}`; $("#design-decision")?.addEventListener("submit", async (decisionEvent) => { decisionEvent.preventDefault(); const d=fields(decisionEvent.target); try { await api(`/disenos/pedidos/${d.order_id}/lineas/${d.line}/versiones/${d.version}/decision`, { method:"POST", body:JSON.stringify({ approved:d.approved === "true", medium:"PORTAL" }) }); notice("Decisión de diseño registrada"); } catch(error){ notice(error.message,true); } }); } catch(error){ notice(error.message,true); } });
  $("#production-action").addEventListener("submit", async (event) => { event.preventDefault(); const x=fields(event.target); const paths={ start:`/produccion/pedidos/${x.order_id}/iniciar`, consume:`/inventario/pedidos/${x.order_id}/consumir`, finish:`/produccion/pedidos/${x.order_id}/completar` }; try { await api(paths[x.action],{ method:"POST" }); notice("Operación de producción completada"); await designs(); } catch(error){ notice(error.message,true); } });
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
