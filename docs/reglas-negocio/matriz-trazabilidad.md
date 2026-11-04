# Matriz de trazabilidad

Los nombres de servicios son contratos de diseño para fases posteriores. No
representan código ya implementado.

| Regla de negocio | Tablas afectadas | Servicio Python previsto | Operación transaccional | Prueba de aceptación |
|---|---|---|---|---|
| Invitado: máximo 5 unidades totales | CLIENTE, PEDIDO, DETALLE_PEDIDO | `OrderService.create_guest_order` | Bloquear cliente sombra, sumar todas las líneas y crear pedido + detalles | 5 permitido; 6 rechazado; varias líneas no evaden el límite |
| Invitado: sin precio mayorista | CLIENTE, ESCALA_PRECIO, DETALLE_PEDIDO | `PricingService.quote_order` | Resolver identidad y precio dentro de la creación del pedido | Invitado que solicita mayorista recibe rechazo |
| Invitado: un pedido activo | CLIENTE, PEDIDO | `OrderService.create_guest_order` | Serializar por cliente y contar estados activos antes de insertar | Dos solicitudes concurrentes producen un solo pedido activo |
| Acceso seguro de invitado | PERSONA, CLIENTE, PEDIDO, REGISTRO_AUDITORIA | `GuestAccessService` | Emitir/verificar credencial opaca y auditar consulta | ID de otro invitado sin credencial no concede acceso |
| Registrado: máximo 2 pendientes de pago | CLIENTE, PEDIDO | `OrderService.create_registered_order` | Bloquear cliente, contar `PENDIENTE_PAGO` e insertar | Tercero rechazado; pedidos pagados no cuentan; carrera no supera 2 |
| Pedido conserva precios históricos | PEDIDO, DETALLE_PEDIDO, ESCALA_PRECIO, PROMOCION | `PricingService.price_order` | Calcular y guardar precio, descuento, importe y modo en detalles | Cambiar catálogo no altera un pedido existente |
| Transición válida e historial | PEDIDO, HISTORIAL_PEDIDO, ETAPA_PROCESO | `OrderStateService.transition` | Validar estado, actualizar pedido e insertar historial | Transición inválida revierte todo; actor y motivo quedan registrados |
| Expiración a las 24 horas | PEDIDO, HITO_PAGO, TRANSACCION, HISTORIAL_PEDIDO | `OrderExpirationService.expire_due_orders` | Bloquear lote vencido, comprobar pagos y marcar una vez | Repetir trabajo no duplica eventos ni expira pedido pagado |
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
| Producción exige aprobación | PEDIDO, VERSION_DISENO, APROBACION_DISENO, HISTORIAL_PEDIDO | `ProductionService.start` | Verificar todas las líneas/versiones y cambiar estado | Sin aprobación, la transacción se rechaza |
| Escalas no se superponen | ESCALA_PRECIO, VARIANTE_PRODUCTO | `PriceScaleService.configure` | Bloquear escalas de variante y validar intervalos | Intervalos contradictorios rechazados |
| Promociones compatibles | PROMOCION, PROMOCION_VARIANTE, DETALLE_PEDIDO | `PromotionService.resolve` | Leer promociones vigentes, aplicar política única y persistir resultado | No acumula incompatibles ni excede descuento permitido |
| Pérdida descuenta una vez | PERDIDA, DETALLE_PERDIDA, MOVIMIENTO_INVENTARIO, ARTICULO_INVENTARIABLE | `LossService.record` | Bloquear artículos, crear salida y detalle enlazado único | Reintento o movimiento ya contado no descuenta dos veces |
| Utilidad sin doble conteo | PEDIDO, DETALLE_PEDIDO, MOVIMIENTO_INVENTARIO, DETALLE_PERDIDA, GASTO, TRANSACCION | `ProfitReportService.calculate` | Consulta consistente de ingresos y costos históricos | Pérdida ya incluida en consumo no vuelve a restarse |
| Permisos de empleados | EMPLEADO, ASIGNACION_ROL, ROL, ROL_PERMISO, PERMISO | `AuthorizationService.require_permission` | Consultar asignación vigente en la misma unidad de trabajo | Empleado sin permiso recibe 403 |
| Cliente solo ve datos propios | CUENTA_ACCESO, CLIENTE, PEDIDO y tablas dependientes | `AuthorizationService.require_owner` | Resolver `auth_uid` a persona; aplicar filtro/RLS | Cliente A no puede consultar B |
| Entrega es distinta de producción | PEDIDO, ENVIO, AGENCIA_ENVIO, HISTORIAL_PEDIDO | `DeliveryService.complete` | Confirmar retiro o entrega real y cambiar estado | Terminar producción no marca entregado |
| Auditoría de acciones críticas | REGISTRO_AUDITORIA y entidad afectada | `AuditService.record` | Insertar auditoría en la misma transacción del cambio | Rollback elimina cambio y auditoría parcial |

La matriz se ampliará con el nombre real de endpoints, restricciones PostgreSQL y
archivos de prueba cuando se implemente cada módulo.
