# Reglas permanentes del proyecto

Estas instrucciones aplican a todo el repositorio.

## Fuente de verdad y alcance

1. Preservar las 41 tablas y sus nombres oficiales. No crear sustitutos ni
   eliminar entidades para simplificar.
2. Priorizar, en este orden: decisiones explícitas del propietario; modelo
   relacional aprobado; script aprobado más reciente; reglas de negocio; MERE y
   UML; documentación preliminar.
3. Tratar `docs/copia - Sublimacion2R.sql` como referencia histórica hasta que el
   propietario confirme su versión y resuelva las discrepancias documentadas.
4. No ejecutar una fase posterior sin autorización expresa del propietario.
5. No modificar archivos de referencia originales. Las conversiones van en
   migraciones nuevas y versionadas.

## Base de datos

- PostgreSQL y Supabase son obligatorios. No validar lógica PostgreSQL solo con
  SQLite.
- `supabase/migrations/` será la fuente canónica del esquema. Alembic, si se
  incorpora, no duplicará ni reescribirá las migraciones SQL canónicas.
- Toda migración debe ser reproducible desde una base vacía y conservar PK, FK,
  UNIQUE, NOT NULL, CHECK e índices aprobados.
- Usar `numeric` para dinero, `timestamptz` en UTC para instantes y presentar
  fechas en `America/Managua`.
- Evitar cascadas sobre datos financieros, históricos y de auditoría.
- Mantener `PEDIDO.total_pedido` y
  `ARTICULO_INVENTARIABLE.existencia_actual` mediante servicios transaccionales.
- No mover reglas comerciales a triggers o procedimientos. Se permiten
  mecanismos PostgreSQL necesarios para integridad, seguridad, RLS e invariantes
  que no puedan quedar expuestas a carreras.

## Backend y transacciones

- Separar API, esquemas Pydantic, servicios, repositorios, modelos y conexión a
  base de datos.
- Colocar reglas comerciales en servicios Python y ejecutar en una sola
  transacción toda operación que afecte varias tablas.
- Aplicar bloqueos de fila o mecanismos equivalentes en límites de pedidos,
  reservas, inventario, confirmación de pagos y operaciones idempotentes.
- Nunca confiar en identificadores de cliente, roles, precios, descuentos o
  importes enviados por el frontend.
- Conservar pagos, reembolsos y compensaciones como historial append-only.
- No integrar pagos reales ni desplegar servicios sin autorización específica.
- Los servicios no hacen `commit`; el endpoint, job o prueba que abre la unidad
  de trabajo es el único responsable de commit y rollback.
- Hasta integrar Supabase Auth, las rutas protegidas permanecen cerradas. No
  añadir encabezados, parámetros ni endpoints de suplantación para desarrollo.
- Resolver permisos de empleado desde EMPLEADO, ASIGNACION_ROL, ROL_PERMISO y
  PERMISO; nunca aceptar roles o permisos declarados por el cliente.

## Seguridad

- Usar Supabase Auth; no almacenar contraseñas propias.
- Aplicar autorización en el servidor y RLS a tablas expuestas por Supabase.
- Mantener buckets privados para diseños y comprobantes; emitir URLs firmadas
  cuando corresponda.
- Nunca guardar secretos, claves de service role, cadenas de conexión reales o
  datos personales reales en el repositorio.
- Usar datos ficticios en seeds y no ejecutarlos en producción.

## Calidad

- Escribir pruebas de las reglas modificadas. Las pruebas de integridad,
  concurrencia, transacciones y RLS deben usar PostgreSQL real aislado.
- Antes de declarar una fase completa: iniciar o compilar lo aplicable, ejecutar
  las pruebas, revisar migraciones e integridad, comprobar secretos y documentar
  resultados reales.
- No afirmar que Supabase, una migración o una prueba funciona sin haberlo
  comprobado.
- Mantener actualizadas la matriz de trazabilidad y las decisiones técnicas.

## Git y entorno

- Trabajar en el checkout existente. No crear worktrees salvo petición expresa.
- Preservar cambios del usuario y revisar `git status` antes y después.
- No borrar datos, reescribir historia, hacer commit, push o publicar sin la
  autorización correspondiente.
