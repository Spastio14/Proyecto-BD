# Resultados de pruebas — Fase 4.2

Fecha: 2026-11-06. Entorno local: PostgreSQL 17.11 en Docker y Python
3.12.14. No se conectó ni escribió en Supabase remoto.

## Resultado final

| Verificación | Resultado |
|---|---|
| `./database/tests/run.sh` | Aprobado: dos reconstrucciones, 41 tablas, 64 FK, RLS y matriz de roles |
| `./backend/tests/run.sh` | 163 aprobadas, 0 fallidas, 2 remotas omitidas por opt-in, 1 aviso externo |
| `ruff check backend` | Aprobado |
| `node --check frontend/app.js` | Aprobado |
| `node --check frontend/dashboard.js` | Aprobado |
| `node --check frontend/activation.js` | Aprobado |
| `git diff --check` | Aprobado |

Las 137 pruebas anteriores permanecen aprobadas. Los dos casos remotos siguen
omitidos porque requieren credenciales privadas y autorización explícita.

## Casos añadidos

- Códigos Auth oficiales: cuenta existente, contraseña, registro deshabilitado,
  correo, confirmación, límites, HTTP 429, red y respuestas inesperadas.
- `/auth/me` obtiene roles y permisos desde PostgreSQL y resuelve el dashboard.
- El registro público rechaza campos de rol y sólo crea clientes.
- Un cliente no puede invitar empleados ni acceder a administración.
- CONTADOR consulta finanzas y compras, pero no crea proveedores ni gestiona roles.
- VENDEDOR gestiona pedidos y clientes, sin reportes financieros ni compras.
- Invitación administrativa sin contraseña, perfil inactivo y activación por JWT.
- Recuperación de invitación parcial sólo con identidad Supabase verificada.
- Prohibición de convertir automáticamente un cliente en empleado o administrador.
- Cambio de rol reemplaza permisos efectivos en consultas posteriores.
- Bootstrap del primer administrador verificado, seguro e idempotente.
- Rutas cliente, admin, contabilidad, ventas y producción servidas correctamente.
- El panel de diseño lista versiones reales y PRODUCCION no puede consultar el directorio de clientes.

## Límites

- Las invitaciones reales, SMTP y bootstrap remoto no se probaron porque
  producirían cambios en Supabase.
- La advertencia `StarletteDeprecationWarning` procede de la combinación
  instalada de FastAPI TestClient y httpx; no causó fallos.
