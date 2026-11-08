const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const presentation = require("../presentation.js");

test("traduce estados y acciones del negocio de forma centralizada", () => {
  assert.equal(presentation.label("PENDIENTE_PAGO"), "Pendiente de pago");
  assert.equal(presentation.label("EN_PRODUCCION"), "En producción");
  assert.equal(presentation.label("CONSUMIR_RESERVAS"), "Registrar consumo de materiales");
  assert.equal(presentation.label("BAJO_PEDIDO"), "Disponible por encargo");
  assert.equal(presentation.label("ESTADO_NUEVO"), "Estado nuevo");
});

test("presenta importes en córdobas y cantidades legibles", () => {
  const amount = presentation.money(1250.5);
  assert.match(amount, /C\$/);
  assert.match(amount, /1[,.]250/);
  assert.match(amount, /50/);
  assert.equal(presentation.quantity(2.5, "UNIDAD"), "2.5 unidad");
  assert.equal(presentation.quantity(2.5, { unidad_medida: "UNIDAD" }), "2.5");
  assert.doesNotMatch(presentation.quantity(2.5, {}), /object Object/);
});

test("presenta fechas en la zona horaria de Managua", () => {
  const value = presentation.date("2026-11-07T15:30:00Z", true);
  assert.match(value, /7/);
  assert.match(value, /nov/i);
  assert.match(value, /2026/);
  assert.match(value, /9:30/);
});

test("oculta códigos internos de permisos en mensajes al usuario", () => {
  const customer = presentation.friendlyError("Falta el permiso PEDIDO_GESTIONAR", false);
  const employee = presentation.friendlyError("No tiene permiso INVENTARIO_AJUSTAR", true);
  assert.equal(customer, "No tienes autorización para realizar esta operación.");
  assert.match(employee, /Solicita acceso al administrador/);
  assert.doesNotMatch(employee, /INVENTARIO_AJUSTAR/);
});

test("omite diseño y producción cuando el pedido no requiere esas etapas", () => {
  const direct = presentation.orderProgressStages({
    estado: "PAGADO",
    requiere_produccion: false,
    historial: [{ estado: "PENDIENTE_PAGO" }, { estado: "PAGADO" }],
  });
  assert.deepEqual(direct.map((stage) => stage.label), ["Solicitud", "Pago", "Listo", "Entregado"]);
  const customized = presentation.orderProgressStages({
    estado: "EN_DISENO",
    requiere_produccion: true,
    historial: [{ estado: "PAGADO" }],
  });
  assert.equal(customized.find((stage) => stage.label === "Diseño").current, true);
  assert.equal(customized.length, 6);
});

test("los pagos nuevos sólo ofrecen transferencia y efectivo", () => {
  const source = fs.readFileSync(path.join(__dirname, "..", "dashboard.js"), "utf8");
  assert.match(source, /Transferencia bancaria/);
  assert.match(source, /Efectivo en caja/);
  assert.doesNotMatch(source, /option value="TARJETA"/);
  assert.doesNotMatch(source, /option value="OTRO"/);
  assert.match(source, /Adjunta manualmente una captura/);
});

test("el sidebar mantiene navegación y cierre accesibles con desplazamiento", () => {
  const styles = fs.readFileSync(path.join(__dirname, "..", "styles.css"), "utf8");
  assert.match(styles, /\.sidebar[^}]*height: 100dvh/);
  assert.match(styles, /\.sidebar nav[^}]*overflow-y: auto/);
  assert.match(styles, /\.sidebar footer[^}]*flex: 0 0 auto/);
});

