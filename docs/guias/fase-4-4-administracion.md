# Fase 4.4 — administración integral

Esta fase conserva las 41 tablas y las cinco migraciones canónicas de Fase 3.
Añade `202611070001_persona_direccion_habitual.sql`, una migración incremental
que incorpora un único atributo nullable a `PERSONA`. La dirección habitual es
el estado actual de contacto; `ENVIO.direccion_entrega` continúa siendo el
snapshot histórico de cada pedido. No se modifica ninguna migración anterior.

## Funcionalidades y API

### Envíos

`GET /api/v1/entregas/pedidos/{id}/datos-iniciales` obtiene nombre, teléfono y
dirección habitual de la persona propietaria del pedido. El formulario permite
editar los tres valores antes de usar `POST /api/v1/entregas/pedidos/{id}`. Los
cambios específicos del envío no sobrescriben la dirección habitual.

### Clientes y condición mayorista

- `GET /api/v1/clientes` devuelve sólo ID y nombre para el directorio compacto.
- `GET /api/v1/clientes/{id}` devuelve ficha, pedidos e historial administrativo.
- `PATCH /api/v1/clientes/{id}` exige `EMPLEADO_GESTIONAR` y sólo acepta datos
  personales autorizados. No acepta correo, roles, UUID ni condición comercial.
- `POST /api/v1/clientes/{id}/condicion-mayorista` autoriza o revoca MAYORISTA,
  exige motivo y `EMPLEADO_GESTIONAR`, y rechaza clientes `INVITADO`.

Cada decisión mayorista queda en `REGISTRO_AUDITORIA`. Los precios aplicados en
`DETALLE_PEDIDO` no se recalculan, por lo que el historial comercial permanece
inalterado.

### Composición y escalas

`GET /catalogo/admin/variantes/{id}/composicion` muestra material, unidad,
cantidad estándar, costo, existencia física, disponibilidad y unidades que
pueden producirse. El endpoint `/requerimientos?cantidad=N` calcula consumo,
faltante y costo para la cantidad elegida.

`POST /catalogo/admin/variantes/{id}/escalas` crea una escala y asigna
`numero_rango = max(numero_rango) + 1` dentro de un bloqueo asesor transaccional
por variante. PostgreSQL conserva además la exclusión contra rangos activos
solapados. `PATCH /escalas/{numero}` edita o desactiva una escala; la interfaz
permite consultar todas antes de cambiarla.

### Pérdidas

`GET /api/v1/perdidas/opciones` publica los momentos, incidentes y etapas válidos.
El formulario permite elegir momento, tipo, pedido, etapa, material, cantidad y
descripción. La confirmación crea `MOVIMIENTO_INVENTARIO.SALIDA_PERDIDA`, enlaza
`DETALLE_PERDIDA` y conserva el costo histórico. Reporte y confirmación quedan
auditados.

### Perfil propio y correo

- `GET /api/v1/perfil` muestra los datos propios y atributos informativos.
- `PATCH /api/v1/perfil` admite nombres, apellidos, teléfono, documento y
  dirección habitual. El esquema estricto rechaza roles, permisos, UUID,
  condición mayorista y otros campos.
- `POST /api/v1/perfil/correo/solicitar` valida que el JWT y
  `CUENTA_ACCESO.identificador_autenticacion` correspondan al mismo perfil y
  solicita el cambio mediante `PUT /auth/v1/user` de Supabase.
- `POST /api/v1/perfil/correo/sincronizar` actualiza `PERSONA` únicamente cuando
  un JWT posterior contiene el nuevo correo verificado para el mismo UUID Auth.

La solicitud inicial no cambia el correo comercial. El usuario debe confirmar
el mensaje de Supabase, volver a iniciar sesión y sincronizar. El servidor no
usa el JWT secret, no almacena tokens y nunca permite editar el UUID.

### Invitaciones

El procedimiento detallado se conserva en
`docs/guias/fase-4-4-invitaciones-empleados.md`. El listado distingue pendiente,
activo, suspendido y solicitud fallida. Los enlaces `invite` y `recovery` siempre
terminan en la validación de UUID, correo, perfil inactivo y rol administrativo.

## Aplicación local

La sexta migración se prueba desde una base PostgreSQL 17 vacía mediante los
runners del repositorio. No se ejecutó sobre Supabase remoto. Antes de aplicarla
en otro entorno se debe revisar el dry-run y autorizar la escritura por separado.
