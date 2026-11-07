# Resultados de pruebas — Fase 4.4

Fecha: 7 de noviembre de 2026 (America/Managua).

La validación se ejecutó contra PostgreSQL 17 local, creado de forma aislada por
`backend/tests/run.sh`. No se conectó ni escribió en Supabase remoto.

## Cobertura añadida

- solicitud inicial aceptada sin afirmar entrega del correo;
- empleado pendiente bloqueado en endpoints protegidos;
- activación con identidad verificada y rechazo de reutilización;
- enlaces Auth de invitación y recuperación;
- reenvío con identidad existente mediante recuperación oficial;
- reintento de una invitación inicial fallida;
- ausencia de duplicados en persona, empleado, cuenta y rol;
- auditoría y estado visual del fallo;
- intervalo local y límite `429` de Supabase;
- rechazo de UUID/correo Auth incongruentes;
- bloqueo de empleados activos y suspendidos;
- autorización del endpoint administrativo;
- concurrencia: sólo una llamada externa para dos reenvíos simultáneos;
- regresión del alta, activación, roles, permisos y dashboards de Fase 4.2;
- encabezados oficiales: clave publicable para recuperación y clave privada sólo
  para operaciones administrativas.
- autocompletado editable de datos de envío desde el cliente del pedido;
- directorio compacto, ficha, edición e historial de clientes;
- autorización y revocación mayorista con auditoría y rechazo de invitados;
- costos, existencias y requerimientos de composición;
- numeración concurrente, edición y desactivación de escalas sin solapamientos;
- captura contextual y trazabilidad de pérdidas e inventario;
- edición del perfil propio y sincronización de correo sólo tras verificar Auth.

## Resultados

```text
Backend: 243 aprobadas, 0 fallidas, 2 omitidas
Frontend: 9 aprobadas, 0 fallidas, 0 omitidas
Preflight Supabase: 15 aprobadas, 0 fallidas, 0 omitidas
Base de datos: 41 tablas y 64 FK verificadas
```

Las dos pruebas omitidas requieren opt-in y credenciales privadas para escribir o
consultar Supabase remoto. Se omitieron deliberadamente porque esta fase prohíbe
modificar el proyecto remoto. La única advertencia es una deprecación de
`TestClient` de Starlette respecto a una futura versión de `httpx`; no afecta el
resultado funcional.

La reconstrucción local, PostgreSQL/RLS y la matriz de roles de Fase 4.2 también
aprobaron. La validación confirmó las cinco migraciones canónicas sin cambios,
la nueva migración incremental de dirección habitual, 41 tablas y 64 claves
foráneas.

Las páginas de clientes y catálogo se revisaron con Chromium en 1280 × 900; las
de pérdidas y perfil, en 390 × 844. Las cuatro vistas mostraron sus formularios,
estados y tablas sin desbordamiento horizontal de la página. La tabla extensa de
pérdidas conserva desplazamiento horizontal interno en móvil.

El flujo con correo real y la aplicación de la migración incremental permanecen
sin ejecutar en Supabase porque esta fase prohíbe modificar el proyecto remoto.
