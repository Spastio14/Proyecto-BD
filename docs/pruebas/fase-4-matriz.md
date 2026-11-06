# Matriz de validación funcional — Fase 4

Fecha: 5 de noviembre de 2026 (`America/Managua`). Los resultados corresponden
a PostgreSQL 17 local. `Pendiente remoto` no equivale a aprobado.

## Clientes, identidad y seguridad

| Regla | Servicio | Tablas | Endpoint | Positivo | Negativos | Evidencia | Clasificación |
|---|---|---|---|---|---|---|---|
| Crear invitado sin Auth | `GuestCoordinator` | PERSONA, CLIENTE | `POST /auth/invitado` | Perfil persistente y cookie | Perfil inactivo | 58, 96, 107 | Implementada y validada |
| Cookie invitada segura | `GuestCredentialSigner` | CLIENTE | Cookie `s2r_guest` | Firma válida | Alterada o vencida | 58–59, 96–97 | Implementada y validada |
| Invitado: máximo 5 unidades | `OrderService` | CLIENTE, PEDIDO, DETALLE_PEDIDO | `POST /pedidos` | 5 y suma multilínea válida | 6, varias líneas >5 | 01–02, 91, 107 | Implementada y validada |
| Invitado: un pedido activo | `OrderService` | CLIENTE, PEDIDO | `POST /pedidos` | Primer pedido | Segundo y carrera | 04, 07, 107 | Implementada y validada |
| Registrado: dos pendientes | `OrderService` | CLIENTE, PEDIDO | `POST /pedidos` | Hasta dos | Tercero y carrera | 05–06, 92 | Implementada y validada |
| Registro y vínculo Auth | `RegistrationCoordinator` | PERSONA, CLIENTE, CUENTA_ACCESO | `POST /auth/registro` | Usuario nuevo | Existente, conflicto local | 60–61, unitarias Signup, 106 | Implementada y validada |
| Recuperación autenticada | `RegistrationCoordinator` | PERSONA, CLIENTE, CUENTA_ACCESO | `POST /auth/completar-registro` | JWT verificado, reintento | Correo de otra persona | 76–78 | Implementada y validada |
| JWT Supabase | `SupabaseTokenVerifier` | CUENTA_ACCESO | Rutas protegidas | Firma/proyecto/audiencia | Vencido, firma/proyecto incorrecto | 51–56 | Implementada y validada |
| Roles desde PostgreSQL | `AuthorizationService` | EMPLEADO, ASIGNACION_ROL, ROL_PERMISO, PERMISO | Rutas de empleado | Permiso vigente | Rol falso o sin permiso | 37, 40, 57, 72 | Implementada y validada |
| Cliente sólo ve lo propio | `OrderService`, `StorageCoordinator` | PEDIDO, VERSION_DISENO, TRANSACCION | GET pedidos/diseños/comprobantes | Propietario | Otro cliente | 36, 69, 73–74, 109 | Implementada y validada |

## Productos, precios y promociones

| Regla | Servicio | Tablas | Endpoint | Positivo | Negativos | Evidencia | Clasificación |
|---|---|---|---|---|---|---|---|
| Precio desde PostgreSQL | `PricingService` | VARIANTE_PRODUCTO | `POST /pedidos`, `/cotizaciones` | C$90 detalle | Precio HTTP ignorado | 09, 39 | Implementada y validada |
| Mayorista autorizado | `PricingService` | CLIENTE, ESCALA_PRECIO | Creación de pedido/cotización | Condición MAYORISTA y rango | Invitado o condición DETALLE | 03, 10, 81–82 | Implementada y validada |
| Rangos sin solapamiento | PostgreSQL + `PricingService` | ESCALA_PRECIO | — | Rango aplicable | Rango activo solapado | 10–11 | Implementada y validada |
| Promoción vigente/aplicable | `PricingService` | PROMOCION, PROMOCION_VARIANTE | `POST /pedidos` | Dos tazas C$170 | Vencida, variante ajena, mínimo | 12–13, 16, 95 | Implementada y validada |
| No acumulación incompatible | `PricingService` | ESCALA_PRECIO, PROMOCION | `POST /pedidos` | Combinación permitida por dato | Mayorista + promo incompatible, exceso | 14, 94 | Implementada y validada |
| Dinero con Decimal/Numeric | `money`, PostgreSQL | PEDIDO, detalles, hitos | Varias | ROUND_HALF_UP | Totales negativos por CHECK | 24–25, 88 | Implementada y validada |
| Catálogo ampliado ficticio | — | PRODUCTO, VARIANTE_PRODUCTO, COMPOSICION | `GET /catalogo` | Taza configurada | Otros productos sin datos aprobados | 46–47 | Pendiente de datos aprobados |

## Cotizaciones, pedidos y estados

| Regla | Servicio | Tablas | Endpoint | Positivo | Negativos | Evidencia | Clasificación |
|---|---|---|---|---|---|---|---|
| Crear cotización sin inventario | `QuotationService` | COTIZACION, DETALLE_COTIZACION | `POST /cotizaciones` | Total y líneas | Variante/cantidad inválida | 41, 88 | Implementada y validada |
| Conversión única | `QuotationService` | COTIZACION, PEDIDO, DETALLE_PEDIDO | `POST /cotizaciones/{id}/convertir` | Aceptada vigente | Ajena, vencida, duplicada, carrera | 42–43, 90, 93 | Implementada y validada |
| Límites al convertir | `QuotationService`, `OrderService` | CLIENTE, PEDIDO | Convertir | Conversión permitida | Invitado >5, tercero pendiente | 83–84 | Implementada y validada |
| Aceptar/rechazar cotización | — | COTIZACION | No existe | Estado preparado en prueba | Sin API/auditoría de decisión | Flujo 106 requiere precondición | Pendiente de implementación |
| Transiciones e historial | `OrderService` | PEDIDO, HISTORIAL_PEDIDO, REGISTRO_AUDITORIA | Cancelación/servicios internos | Transición permitida | Salto inválido | 44, 48, 50, 89, 106 | Implementada y validada |
| Expiración 24 h | `OrderExpirationService` | PEDIDO, TRANSACCION, HISTORIAL_PEDIDO | Job `expire_orders` | Expira una vez | Pago verificado/revisión vigente | 44–45 | Implementada y validada |
| Cancelación libera reserva | `OrderService` | CANCELACION, RESERVA_INVENTARIO, PEDIDO | `POST /pedidos/{id}/cancelar` | Primera cancelación | Ajena, duplicada, estado terminal | 21–22 | Implementada y validada |
| Entrega distinta de producción | — | PEDIDO, ENVIO | No existe | — | No debe marcarse entregado al producir | Estados separados en esquema | Pendiente de implementación |

## Pagos e inventario

| Regla | Servicio | Tablas | Endpoint | Positivo | Negativos | Evidencia | Clasificación |
|---|---|---|---|---|---|---|---|
| Hitos y anticipo 50 % | `OrderService` | HITO_PAGO, PEDIDO | Crear pedido | Anticipo/saldo | Redondeo impar | 24–25 | Implementada y validada |
| Reportado ≠ verificado | `PaymentService` | TRANSACCION, HITO_PAGO, PEDIDO | `POST /pagos/pedidos/{id}/reportar` | Reporte pendiente | Sin reserva/avance | 17, 26–27, 98 | Implementada y validada |
| Verificación autorizada | `PaymentService` | TRANSACCION, PEDIDO, AUDITORIA | `POST /pagos/{id}/confirmar` | Empleado con permiso | Cliente/sin permiso/tardío | 27, 37, 49 | Implementada y validada |
| Idempotencia de reporte | `PaymentService` | TRANSACCION | Reportar | Misma clave/mismo resultado | Clave en otro pedido, carrera | 29, 86 | Implementada y validada |
| Confirmación idempotente | `PaymentService` | TRANSACCION, HITO_PAGO, RESERVA | Confirmar | Reintento | Estado rechazado, carrera | 28, 99 | Implementada y validada |
| Rechazo de pago | `PaymentService.reject` | TRANSACCION, AUDITORIA | No existe | Estado RECHAZADO | Segunda resolución | 98 | Implementada con API insuficiente |
| Reserva tras anticipo | `PaymentService`, `InventoryReservationService` | RESERVA_INVENTARIO, ARTICULO_INVENTARIABLE | Confirmar | Reserva completa | Reportado, inventario insuficiente | 18, 23, 26–27 | Implementada y validada |
| No sobreventa | `InventoryReservationService` | ARTICULO_INVENTARIABLE, RESERVA | Confirmar | Una reserva compatible | Dos pedidos por últimas unidades | 19 | Implementada y validada |
| Disponibilidad consistente | `InventoryService` | ARTICULO_INVENTARIABLE, RESERVA | `GET /inventario/.../disponibilidad` | Existencia menos reservas | Artículo inexistente | 100 | Implementada y validada |
| Consumo único | `InventoryService` | RESERVA, MOVIMIENTO_INVENTARIO, ARTICULO | `POST /inventario/pedidos/{id}/consumir` | Primer consumo | Reintento/insuficiencia | 20, 23, 100 | Implementada y validada |
| Compra confirmada ingresa stock | — | COMPRA, DETALLE_COMPRA, MOVIMIENTO_INVENTARIO | No existe | — | Duplicado/concurrencia sin servicio | Sólo integridad estructural | Pendiente de implementación |
| Reembolso append-only | — | CANCELACION, REEMBOLSO, TRANSACCION | No existe | — | Compensación duplicada | Sólo integridad estructural | Pendiente de implementación |

## Diseño, producción, pérdidas y Storage

| Regla | Servicio | Tablas | Endpoint | Positivo | Negativos | Evidencia | Clasificación |
|---|---|---|---|---|---|---|---|
| Versionado exacto | `DesignService` | VERSION_DISENO | Carga multipart | Versiones 1 y 2 | Carrera de numeración | 32, 87 | Implementada y validada |
| Decisión vigente | `DesignService`, `ProductionService` | VERSION_DISENO, APROBACION_DISENO | Decisión/iniciar | Última versión aprobada | Pendiente, reemplazada o rechazada | 31–32, 48, 85 | Implementada y validada |
| Producción exige anticipo | `ProductionService` | HITO_PAGO, PEDIDO | `POST /produccion/.../iniciar` | Pago y diseño | Sin anticipo/permiso | 31, 37, 48, 106 | Implementada y validada |
| Registrar pérdida | `LossService` | PERDIDA | `POST /perdidas` | Momento/tipo/motivo | Catálogo o motivo inválido | 33–35, 108 | Implementada y validada |
| Confirmar pérdida una vez | `LossService` | DETALLE_PERDIDA, MOVIMIENTO, ARTICULO | `POST /perdidas/{id}/confirmar` | Salida y costo | Sin líneas, exceso, carrera | 33, 101–102 | Implementada y validada |
| Contexto obligatorio de pérdida | `LossService` | PERDIDA, PEDIDO, ETAPA | Reportar | Asociación posible | Regla exacta no definida | 34, 108 | Implementada con regla insuficiente |
| Formato y tamaño de archivos | `StorageCoordinator` | VERSION_DISENO, TRANSACCION | Cargas multipart | PNG/JPEG/PDF | MIME, firma, extensión, tamaño | 64–65, 103–104 | Implementada y validada |
| Storage privado y propiedad | `StorageCoordinator` | PEDIDO, VERSION_DISENO, TRANSACCION | URL firmada | Propietario/empleado autorizado | Otro cliente | 69, 73–75, 109 | Implementada y validada |
| Compensación de objeto nuevo | `StorageCoordinator` | VERSION_DISENO, TRANSACCION | Carga | Persistencia correcta | Fallo DB, carrera de reemplazo | 66, 68, 105 | Implementada y validada |

## PostgreSQL, auditoría y rendimiento

| Regla | Responsable | Tablas | Evidencia | Clasificación |
|---|---|---|---|---|
| 41 tablas y 64 FK | Migraciones canónicas | Todas | `database/tests/run.sh` | Implementada y validada |
| CHECK, UNIQUE, NOT NULL y FK | PostgreSQL | Todas | 12 aserciones SQL y pruebas de error | Implementada y validada |
| RLS/privilegios | Migraciones RLS | Tablas públicas/privadas | runner SQL, casos 47 y 70 | Implementada y validada |
| Auditoría en misma transacción | `AuditService` | REGISTRO_AUDITORIA | 30, 44, 49, 106 | Implementada y validada |
| Consultas sin N+1 | Rutas/repositorios | Catálogo y listados | Revisión de consultas | Implementada y validada para rutas actuales |
| Índices con volumen real | Migraciones futuras | Historial y reportes | Seed insuficiente para benchmark | Implementada con pruebas insuficientes |
| Reportes y utilidad neta | No implementado | PEDIDO, MOVIMIENTO, PERDIDA, GASTO | Sin servicio | Pendiente de implementación |

## Pendientes remotos

| Comprobación | Resultado |
|---|---|
| PostgreSQL remoto 17 y esquema esperado | Omitida; requiere `RUN_SUPABASE_REMOTE_TESTS=1` y URL privada |
| Historial remoto de cinco migraciones | Omitida; requiere CLI enlazado y token |
| Auth/Storage real extremo a extremo | Pendiente de ejecución controlada por el propietario |

No se ejecutó ninguna escritura remota durante Fase 4.
