import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const code = fs.readFileSync(path.resolve("frontend/dashboard.js"), "utf8");

test("cancelForm se renderiza inmediatamente antes de <h2>Activos</h2>", () => {
  assert.match(
    code,
    /setContent\("Pedidos",\s*`\$\{cancelForm\}<h2>Activos<\/h2>/,
    "El cancelForm debe preceder inmediatamente al encabezado <h2>Activos</h2>"
  );
});

test("cancelForm requiere el permiso PEDIDO_GESTIONAR", () => {
  assert.match(
    code,
    /const cancelForm\s*=\s*permitted\("PEDIDO_GESTIONAR"\)\s*&&/,
    "Debe validar permitted('PEDIDO_GESTIONAR')"
  );
});

test("cancelForm solo incluye pedidos no finalizados y tiene motivo required", () => {
  assert.match(
    code,
    /rows\.filter\(\(row\)\s*=>\s*!\["CANCELADO","ENTREGADO","EXPIRADO"\]\.includes\(row\.estado\)\)/,
    "Debe filtrar los pedidos cancelables"
  );
  assert.match(
    code,
    /<input name="reason" maxlength="500" required>/,
    "El motivo debe ser obligatorio con longitud máxima 500"
  );
});

test("el listener de admin-order-cancel llama al endpoint correcto con confirmación y motivo", () => {
  assert.match(
    code,
    /api\(`\/pedidos\/\$\{x\.id\}\/cancelar`,\s*\{\s*method:"POST",\s*body:JSON\.stringify\(\{\s*reason:x\.reason\s*\}\)/,
    "Debe enviar POST a /pedidos/{id}/cancelar con el motivo ingresado"
  );
  assert.match(
    code,
    /confirm\("¿Confirmas la cancelación administrativa\?/,
    "Debe pedir confirmación previa"
  );
  assert.match(
    code,
    /notice\("Cancelación administrativa registrada"\);\s*await orders\(\);/,
    "Debe emitir notificación y refrescar orders()"
  );
});

test("showOrderDetail llama a bindOrderDetails después de setContent para activar el formulario", () => {
  // Debe contener setContent(`Pedido ...`), luego $(".back-link")..., y luego bindOrderDetails()
  assert.match(
    code,
    /setContent\(`Pedido \$\{order\.codigo\}`[\s\S]*?\$\("\.back-link"\)\.addEventListener[\s\S]*?bindOrderDetails\(\);/,
    "showOrderDetail debe llamar a bindOrderDetails() tras renderizar el detalle"
  );
});

test("bindOrderDetails registra submit sobre .order-cancel-form y previene duplicaciones al reemplazar DOM", () => {
  assert.match(
    code,
    /document\.querySelectorAll\("\.order-cancel-form"\)\.forEach\(\(form\)\s*=>\s*form\.addEventListener\("submit"/,
    "bindOrderDetails debe registrar el submit sobre .order-cancel-form"
  );
  // Al usar setContent(), el innerHTML de #content es sustituido íntegramente,
  // por lo que cada reapertura de detalle instancia un nuevo formulario sin acumular listeners.
  assert.match(
    code,
    /function setContent\(title, html\) \{\s*\$\("#view-title"\)\.textContent = title;\s*\$\("#content"\)\.innerHTML = html;/,
    "setContent reemplaza innerHTML asegurando que no se acumulen listeners previos"
  );
});


