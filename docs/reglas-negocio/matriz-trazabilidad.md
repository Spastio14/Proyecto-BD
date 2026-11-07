# Matriz de trazabilidad

Los nombres de servicios son contratos de diseño para fases posteriores. No
representan código ya implementado.

| Regla de negocio | Tablas afectadas | Servicio Python previsto | Operación transaccional | Prueba de aceptación |
|---|---|---|---|---|
| Invitado: máximo 5 unidades totales | CLIENTE, PEDIDO, DETALLE_PEDIDO | `OrderService.create_guest_order` | Bloquear cliente sombra, sumar todas las líneas y crear pedido + detalles | 5 permitido; 6 rechazado; varias líneas no evaden el límite |
| Invitado: sin precio mayorista | CLIENTE, ESCALA_PRECIO, DETALLE_PEDIDO | `PricingService.quote_order` | Resolver identidad y precio dentro de la creación del pedido | Invitado que solicita mayorista recibe rechazo |
| Invitado: un pedido activo | CLIENTE, PEDIDO | `OrderService.create_guest_order` | Serializar por cliente y contar PENDIENTE_PAGO, PAGADO_PARCIAL, PAGADO, EN_DISENO, EN_PRODUCCION y LISTO antes de insertar | Dos solicitudes concurrentes producen un solo pedido activo |
| Acceso seguro de invitado | PERSONA, CLIENTE, PEDIDO, REGISTRO_AUDITORIA | `GuestAccessService` | Emitir/verificar cookie firmada Secure/HttpOnly y token UUID no predecible; auditar consulta | ID o token de otro invitado sin cookie válida no concede acceso |
| Registrado: máximo 2 pendientes de pago | CLIENTE, PEDIDO | `OrderService.create_registered_order` | Bloquear cliente, contar `PENDIENTE_PAGO` e insertar | Tercero rechazado; pedidos pagados no cuentan; carrera no supera 2 |
| Pedido conserva precios históricos | PEDIDO, DETALLE_PEDIDO, ESCALA_PRECIO, PROMOCION | `PricingService.price_order` | Calcular y guardar precio, descuento, importe y modo en detalles | Cambiar catálogo no altera un pedido existente |
| Transición válida e historial | PEDIDO, HISTORIAL_PEDIDO, ETAPA_PROCESO | `OrderStateService.transition` | Validar estado, actualizar pedido e insertar historial | Transición inválida revierte todo; actor y motivo quedan registrados |
| Expiración a las 24 horas | PEDIDO, HITO_PAGO, TRANSACCION, HISTORIAL_PEDIDO | `OrderExpirationService.expire_due_orders` | Bloquear lote vencido, comprobar pagos y marcar una vez | Repetir trabajo no duplica eventos ni expira pedido pagado |
| Una sola revisión de pago por 24 horas | PEDIDO, TRANSACCION, HISTORIAL_PEDIDO | `PaymentReviewService.start_or_expire` | Bajo bloqueo, fijar `fecha_inicio_revision_pago` solo si es NULL; no avanzar ni reservar; expirar al vencer | Reintento no reinicia el plazo; segundo reporte no crea prórroga indefinida |
| Pago verificado tardío requiere administración | TRANSACCION, PEDIDO, REGISTRO_AUDITORIA | `PaymentService.confirm_late` | Exigir permiso administrativo, confirmar e historiar en una transacción | Empleado común no reactiva; administración deja actor y motivo |
| Cotización no toca inventario | COTIZACION, DETALLE_COTIZACION | `QuotationService.create` | Crear cabecera y líneas | Existencias y reservas permanecen iguales |
| Pedido nuevo no reserva inventario | PEDIDO, DETALLE_PEDIDO, RESERVA_INVENTARIO | `OrderService.create_order` | Crear pedido sin reservas | No aparece reserva antes del anticipo confirmado |
| Anticipo confirmado reserva inventario | HITO_PAGO, TRANSACCION, PEDIDO, ARTICULO_INVENTARIABLE, COMPOSICION_PRODUCTO, RESERVA_INVENTARIO | `PaymentService.confirm` + `InventoryReservationService.reserve` | Verificar pago, bloquear artículos, validar disponible y crear reservas | 50 % confirmado reserva una vez; pago reportado no reserva |
| No sobreventa | ARTICULO_INVENTARIABLE, RESERVA_INVENTARIO | `InventoryReservationService.reserve` | Bloquear artículos en orden estable y comparar existencia menos reservas activas | Dos pedidos por última unidad: solo uno reserva |
| Cancelación libera una vez | CANCELACION, PEDIDO, RESERVA_INVENTARIO, HISTORIAL_PEDIDO | `CancellationService.cancel_order` | Autorizar, cancelar, liberar reservas activas e historiar | Segundo intento no incrementa stock ni duplica liberación |
| Movimiento de inventario idempotente | MOVIMIENTO_INVENTARIO, RESERVA_INVENTARIO, COMPRA, DETALLE_COMPRA | `InventoryMovementService.apply` | Comprobar origen único, insertar movimiento y actualizar saldo | Reintento no crea segundo movimiento |
| Compra confirmada ingresa stock una vez | COMPRA, DETALLE_COMPRA, MOVIMIENTO_INVENTARIO, ARTICULO_INVENTARIABLE | `PurchaseService.confirm` | Bloquear compra y artículos, crear entradas y actualizar saldos | Confirmación repetida no duplica existencias |
| Pago reportado ≠ confirmado | HITO_PAGO, TRANSACCION, PEDIDO | `PaymentService.report` / `confirm` | Reportar append-only; confirmar con empleado autorizado | Reporte no avanza estado ni reserva |
| Operación financiera idempotente | TRANSACCION, HITO_PAGO | `PaymentService` | Insertar por `clave_idem` única y devolver resultado previo al reintentar | Misma clave produce un solo efecto económico |
| Reembolso mediante compensación | CANCELACION, REEMBOLSO, TRANSACCION | `RefundService.issue` | Crear reembolso y transacción compensatoria enlazada | Historial original permanece y saldo cuadra |
| Anticipo normal mínimo 50 % | PEDIDO, HITO_PAGO, TRANSACCION | `PaymentPolicyService` | Calcular con Decimal y redondeo acordado antes de confirmar | Casos pares, impares y redondeo monetario correctos |
| Diseño aprobado por versión exacta | VERSION_DISENO, APROBACION_DISENO, PEDIDO | `DesignApprovalService.approve` | Bloquear versión e insertar aprobación vinculada | Aprobar V1 no autoriza V2 |
| Producción exige anticipo y aprobación | PEDIDO, HITO_PAGO, TRANSACCION, VERSION_DISENO, APROBACION_DISENO, HISTORIAL_PEDIDO | `ProductionService.start` | Verificar anticipo confirmado y todas las líneas/versiones; cambiar estado sin regresión | Sin pago o aprobación vigente, la transacción se rechaza |
| Escalas no se superponen | ESCALA_PRECIO, VARIANTE_PRODUCTO | `PriceScaleService.configure` | Bloquear escalas de variante y validar intervalos | Intervalos contradictorios rechazados |
| Promociones compatibles | PROMOCION, PROMOCION_VARIANTE, DETALLE_PEDIDO | `PromotionService.resolve` | Leer promociones vigentes, aplicar política única y persistir resultado | No acumula incompatibles ni excede descuento permitido |
| Pérdida descuenta una vez | PERDIDA, DETALLE_PERDIDA, MOVIMIENTO_INVENTARIO, ARTICULO_INVENTARIABLE | `LossService.record` | Bloquear artículos, crear salida y detalle enlazado único | Reintento o movimiento ya contado no descuenta dos veces |
| Utilidad sin doble conteo | PEDIDO, DETALLE_PEDIDO, MOVIMIENTO_INVENTARIO, DETALLE_PERDIDA, GASTO, TRANSACCION | `ProfitReportService.calculate` | Consulta consistente de ingresos y costos históricos | Pérdida ya incluida en consumo no vuelve a restarse |
| Permisos de empleados | EMPLEADO, ASIGNACION_ROL, ROL, ROL_PERMISO, PERMISO | `AuthorizationService.require_permission` | Consultar asignación vigente en la misma unidad de trabajo | Empleado sin permiso recibe 403 |
| Cliente solo ve datos propios | CUENTA_ACCESO, CLIENTE, PEDIDO y tablas dependientes | `AuthorizationService.require_owner` | Resolver `auth_uid` a persona; aplicar filtro/RLS | Cliente A no puede consultar B |
| Entrega es distinta de producción | PEDIDO, ENVIO, AGENCIA_ENVIO, HISTORIAL_PEDIDO | `DeliveryService.complete` | Confirmar retiro o entrega real y cambiar estado | Terminar producción no marca entregado |
| Auditoría de acciones críticas | REGISTRO_AUDITORIA y entidad afectada | `AuditService.record` | Insertar auditoría en la misma transacción del cambio | Rollback elimina cambio y auditoría parcial |

## Implementación de Fase 2

| Área | Implementación | Evidencia PostgreSQL |
|---|---|---|
| Clientes y límites | `CustomerService`, `OrderService`; bloqueo de CLIENTE antes de contar | `test_orders_pricing.py` casos 01–08 |
| Precios y promociones | `PricingService`; valores leídos de variante, escala y promoción | casos 09–16 |
| Pagos y reservas | `PaymentService`, `InventoryReservationService`; una transacción | `test_payments_inventory.py` casos 17–30 |
| Diseños y producción | `DesignService`, `ProductionService`; última versión exacta | `test_production_loss_security.py` casos 31–32 y caso 48 |
| Pérdidas | `LossService`; movimiento UQ y costo histórico | casos 33–35 |
| Propiedad y seguridad | proveedor cerrado, propiedad por persona y permisos desde roles | casos 36–40 |
| Cotizaciones | `QuotationService`; conversión bloqueada y UQ | casos 41–43 |
| Expiración | `OrderExpirationService`; `SKIP LOCKED` e historial idempotente | casos 44–45 |
| API/OpenAPI | routers por módulo, salud y catálogo sin escalas mayoristas | casos 46–47 |
| Pago tardío y no regresión | permiso administrativo separado; pagos posteriores no bajan EN_PRODUCCION | casos 49–50 |

## Implementación de Fase 3

| Área | Implementación | Evidencia |
|---|---|---|
| JWT y cuenta | JWKS, issuer/audience/exp y vínculo CUENTA_ACCESO activo | casos 51–57 |
| Invitado | cookie cifrada/autenticada Secure/HttpOnly y perfil INVITADO activo | casos 58–59 |
| Registro | Auth externo, transacción local y recuperación mediante JWT verificado, sin borrar usuarios | casos 60–61 y 76–78 |
| PostgreSQL alojado | TLS obligatorio y compatibilidad con transaction pooler | casos 62–63 |
| Diseños | bucket privado, VERSION_DISENO y compensación | casos 64–66, 69 |
| Comprobantes | bucket privado y referencia coherente en TRANSACCION | casos 67–68 |
| RLS | datos privados cerrados a Data API | caso 70 y runner estructural |
| Proyecto alojado | versión, esquema e historial de migraciones | casos 76–77 pendientes de opt-in remoto |

## Validación integral de Fase 4

La matriz detallada y sus clasificaciones se encuentran en
`docs/pruebas/fase-4-matriz.md`. Fase 4 añadió los casos 81–109, con 32
ejecuciones por la parametrización de formatos de archivo.

| Área | Evidencia añadida | Resultado |
|---|---|---|
| Mayorista autorizado | casos 81–82 | Requiere tipo elegible y `condicion_comercial = MAYORISTA` |
| Límites al convertir cotización | casos 83–84, 93 | Comparte bloqueo y reglas con creación directa |
| Diseño vigente | casos 85 y 87 | Un rechazo posterior bloquea producción; versionado concurrente consecutivo |
| Pagos concurrentes | casos 86 y 99 | Reporte y confirmación idempotentes con conexiones independientes |
| Límites concurrentes | casos 92–93 | Registrados y conversiones no superan sus máximos |
| Cookies y Storage | casos 96–97 y 103–105 | Expiración, atributos, formatos y reemplazo concurrente compensado |
| Inventario y pérdidas | casos 98, 100–102, 108 | Rechazo sin reserva, disponibilidad, costo y confirmación única |
| Flujos A–E | casos 106–109 más carreras 19/86/87/92/93/99/101/105 | Núcleo comercial y aislamiento validados localmente |

## Sistema funcional de Fase 4.1

| Área | Implementación | Evidencia |
|---|---|---|
| Cotizaciones | decisión aceptar/rechazar y conversión con propiedad, estado y vencimiento | casos 110–111 |
| Pedidos | detalles, historial y transiciones autorizadas; operaciones específicas conservan sus reglas | caso 111 y regresión 106–109 |
| Pagos | consulta, listado por pedido, confirmación y rechazo con permisos | caso 120 y regresión 86, 98–100 |
| Compras | borrador, detalles, total, confirmación atómica y entrada única | casos 112–114, 117–118 |
| Entrega | programación para envío y finalización sólo desde LISTO | caso 115 |
| Reportes | resumen API y 18 consultas SQL de lectura | caso 116 y runner PostgreSQL |
| Interfaz | HTML/CSS/JS servido por FastAPI, JWT Supabase y datos API reales | caso 116 y validación de sintaxis JS |

Los reembolsos permanecen pendientes porque faltan porcentajes de retención,
autoridad, estados elegibles, método de devolución y tratamiento de pagos
parciales. No se calcula utilidad neta hasta aprobar la asignación de compras,
pérdidas, gastos, retenciones y reembolsos al periodo contable.

## Autenticación y roles de Fase 4.2

| Regla | Implementación | Evidencia |
|---|---|---|
| Registro público sólo de clientes | esquema estricto y `RegistrationCoordinator` | caso 130 y regresión de registro |
| Identidad efectiva | `GET /auth/me` consulta cuenta, perfil, roles y permisos | casos 121–122 y 133 |
| Invitación sin contraseña | `EmployeeInvitationCoordinator` y API Admin Auth | caso 125 |
| Activación verificada | JWT Supabase + invitación EMPLEADO inactiva | casos 125–126 |
| No convertir clientes | validación en invitación y bootstrap | casos 127 y 132 |
| Administración inicial | comando manual verifica UUID con API Auth | casos 131–132 |
| Menor privilegio | matriz DML y permisos separados por operación | casos 123–124 y runner SQL |
| Permisos dinámicos | asignaciones activas se consultan por petición | caso 128 |
| Dashboard por perfil | prioridad de roles sin confiar en el navegador | casos 121–122 y 133 |

## Operación integral de Fase 4.3

| Regla | Implementación | Evidencia |
|---|---|---|
| Saldo financiero visible | `PaymentService.summary` separa exigido, pendiente, verificado y restante | casos 31–35 de pagos |
| Un pendiente por hito | bloqueo de pedido e hito antes de reportar | caso 31 y carrera 35 |
| Catálogo administrativo | `CatalogAdminService` y permiso `CATALOGO_GESTIONAR` | casos 201–202 |
| Inventario por movimientos | alta en cero, compra o ajuste autorizado y auditado | casos 203 y 207 |
| Escalas no solapadas | validación de servicio más exclusión PostgreSQL | caso 204 |
| Receta histórica | composición protegida hasta crear la reserva; reserva como snapshot | caso 205 |
| Composición completa | requerimientos, faltante y costo por cantidad | casos 205–206 |
| Fin de producción controlado | reservas agotadas antes de pasar a `LISTO` | caso 208 |
| Entrega con saldo pagado | todos los hitos deben estar `PAGADO` | caso 209 |
| Resumen operativo | `/pedidos/{id}/operacion` calcula siguiente acción | casos 210 y 213 |
| Sin salto genérico a LISTO | transición disponible sólo por `ProductionService.complete` | caso 211 |
| Tablero administrativo | KPIs de periodo, stock bajo y auditoría reciente | casos 214–215 |
| Modelo conservado | metadatos ORM contienen exactamente 41 tablas | caso 216 |
| Interfaz por módulos | navegación y endpoints operativos protegidos | casos 217–218 |

## Invitaciones de empleados de Fase 4.4

| Regla | Implementación | Evidencia |
|---|---|---|
| Perfil pendiente sin acceso | `EMPLEADO.INACTIVO` sigue bloqueado aunque exista JWT y `CUENTA_ACCESO` | `test_pending_employee_cannot_authenticate_protected_requests` |
| Activación verificada | UUID, correo, rol e invitación pendiente se validan antes de pasar a `ACTIVO` | `test_activation_requires_verified_identity_and_link_cannot_be_reused` |
| Reenvío sin duplicados | operación explícita usa recuperación o invitación según exista identidad Auth | `test_resend_for_existing_identity_uses_recovery_without_duplicates` y `test_failed_initial_request_can_be_retried_without_duplicate_profile` |
| Identidad exacta | API administrativa confirma UUID y correo antes de solicitar recuperación | `test_resend_rejects_auth_identity_with_different_email` |
| Control de abuso | bloqueo asesor por empleado, intervalo local y propagación segura de `429` | `test_resend_rate_limit_blocks_repeated_request_before_supabase` y `test_concurrent_resend_allows_only_one_external_request` |
| Estados fiables | panel distingue pendiente, activo, suspendido y fallo confirmado sin afirmar entrega | `test_initial_invitation_is_pending_and_never_claims_email_delivery` y prueba frontend |
| Auditoría | solicitud, aceptación y fallo se registran sin tokens ni contraseñas | `test_failed_resend_is_audited_and_exposed_as_failed_state` |
| Menor privilegio | sólo `EMPLEADO_GESTIONAR` puede reenviar y activos/suspendidos quedan bloqueados | pruebas del endpoint y `test_resend_is_blocked_for_active_or_suspended_employee` |

## Administración integral de Fase 4.4

| Regla | Implementación | Evidencia |
|---|---|---|
| Datos iniciales de envío | contacto habitual desde `PERSONA`; `ENVIO` conserva el snapshot editable | `test_delivery_defaults_use_customer_usual_address_and_remain_editable` y `test_delivery_keeps_edited_recipient_snapshot` |
| Directorio y ficha de cliente | lista compacta, detalle, pedidos, historial y edición administrativa | `test_customer_directory_is_compact_and_detail_contains_history` |
| Mayorista elegible | sólo REGISTRADO/EMPRESA, motivo y auditoría; INVITADO rechazado | `test_wholesale_condition_rejects_guests_and_preserves_historical_prices` |
| Receta comprensible | material, consumo, costos, existencias, capacidad y requerimientos | `test_composition_overview_exposes_material_cost_stock_and_capacity` |
| Número de escala automático | bloqueo asesor por variante y exclusión PostgreSQL contra solapamiento | pruebas de creación, edición y concurrencia de escalas Fase 4.4 |
| Pérdida contextual | opciones válidas, pedido/etapa y salida de inventario trazable | `test_loss_options_and_selected_context_are_audited` |
| Perfil de menor privilegio | esquema estricto de datos personales y correo confirmado por UUID Auth | pruebas de perfil y cambio de correo Fase 4.4 |
| Modelo conservado | columna nullable incremental en `PERSONA`, sin tablas nuevas | runner estructural: 41 tablas y 64 FK |

## Consumo de reservas de producción — post Fase 4.4

| Regla | Implementación | Evidencia |
|---|---|---|
| Permiso mínimo de consumo | `INVENTARIO_CONSUMIR_RESERVAS` sólo se asigna a ADMINISTRADOR y PRODUCCION | migración `202611070002` y prueba de matriz de roles |
| Administración separada | PRODUCCION conserva consulta y consumo, pero no `INVENTARIO_GESTIONAR` | `test_production_cannot_administer_inventory` |
| Estado estricto | sólo pedidos `EN_PRODUCCION` aceptan el consumo | prueba parametrizada de estados incompatibles |
| Consumo exactamente una vez | bloqueo de pedido, reservas y artículos; movimiento previo se reutiliza | `test_concurrent_consumption_discount_is_exactly_once` |
| Inventario y reserva coherentes | `SALIDA_PRODUCCION`, existencia 18→17 y reserva `AGOTADA/0` | `test_production_can_start_consume_once_and_complete` |
| Finalización controlada | pedido con reservas pendientes o ausentes no pasa a `LISTO` | pruebas de reservas pendientes y faltantes |
| Interfaz por estado y permiso | resumen operativo expone acciones permitidas y el panel elimina opciones fijas | prueba frontend `producción muestra sólo acciones operativas autorizadas` |
