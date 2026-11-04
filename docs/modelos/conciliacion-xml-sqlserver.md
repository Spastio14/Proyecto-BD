# Conciliación definitiva entre XML y SQL Server

Fecha: 4 de noviembre de 2026 (`America/Managua`).

Alcance: comparación estática entre `docs/S2R_BD.drawio.xml` y
`docs/copia - Sublimacion2R.sql`. Las fuentes originales no fueron modificadas y
no se creó DDL PostgreSQL.

## 1. Procedencia y autoridad

El historial disponible contiene un único commit que incorpora ambas fuentes:
`6611604622190a2c945c7003a1a0407e92deeffe`, mensaje `documentos de
referencia`, autor Roger Romero, 4 de noviembre de 2026. No hay tags, nombres de
archivo, encabezados ni commits anteriores que permitan demostrar que el SQL es
“V3.0”. En adelante se denomina **versión SQL Server encontrada**.

El XML y el SQL coinciden en las 41 tablas. Para PostgreSQL se propone esta
prioridad:

1. decisiones explícitas del propietario y reglas maestras;
2. nombres completos y estructura conceptual del XML;
3. restricciones y tipos de la versión SQL Server encontrada, cuando no
   contradigan el XML o las reglas;
4. seeds y consultas únicamente como ejemplos históricos.

## 2. Resultado general

| Elemento | XML | SQL Server encontrado | Resolución propuesta |
|---|---:|---:|---|
| Tablas | 41 | 41 | Conservar exactamente las 41 |
| Relaciones/FK declaradas | 63 | 64 | Revisar FK 64; no decidir por el conteo |
| Columnas con nombre abreviado | — | 57 ocurrencias verificadas | Usar el nombre completo del XML |
| Columnas presentes solo en SQL | — | 7 | Resolver por regla de negocio y aprobación |
| Diferencias de nulabilidad | 38 | 38 | Resolver por ciclo de vida y cardinalidad |
| Índices | no especificados | 46 | Revalidar para patrones PostgreSQL |
| Triggers/procedimientos/vistas | 0 | 0 | Mantener lógica comercial en FastAPI |

La cifra “48 atributos abreviados” fue una estimación de la auditoría preliminar.
La comparación por tabla y posición encuentra **57 ocurrencias**. El SQL contiene
56 comentarios `nombre completo` y tres abreviaciones adicionales en `PERSONA`;
dos comentarios no coinciden con el XML (`PROVEEDOR.correo` y
`DETALLE_COMPRA.importe`), lo que explica que contar comentarios tampoco produzca
el resultado correcto. La tabla siguiente es la evidencia canónica propuesta.

## 3. Equivalencias de nombres para PostgreSQL

Todos los nombres completos siguientes caben en el límite PostgreSQL de 63 bytes
y usan `snake_case` sin palabras reservadas problemáticas.

| Tabla | SQL Server encontrado | Nombre PostgreSQL propuesto |
|---|---|---|
| PERSONA | `tel` | `telefono_contacto` |
| PERSONA | `correo` | `correo_electronico` |
| PERSONA | `documento` | `documento_identificacion` |
| CUENTA_ACCESO | `auth_uid` | `identificador_autenticacion` |
| CUENTA_ACCESO | `fec_alta` | `fecha_activacion` |
| CUENTA_ACCESO | `ult_acceso` | `ultimo_acceso` |
| CLIENTE | `fec_registro` | `fecha_registro` |
| EMPLEADO | `max_asignaciones` | `capacidad_maxima_asignaciones` |
| ASIGNACION_ROL | `fec_asig` | `fecha_asignacion` |
| ASIGNACION_ROL | `fec_fin` | `fecha_finalizacion` |
| COTIZACION | `fec_emision` | `fecha_emision` |
| COTIZACION | `fec_venc` | `fecha_vencimiento` |
| PEDIDO | `id_emp_reg` | `id_empleado_registro` |
| PEDIDO | `fec_crea` | `fecha_creacion` |
| PEDIDO | `fec_entrega_prev` | `fecha_entrega_prevista` |
| HISTORIAL_PEDIDO | `fec_hora` | `fecha_hora` |
| DETALLE_PEDIDO | `precio_unit` | `precio_unitario_aplicado` |
| DETALLE_PEDIDO | `descuento` | `descuento_aplicado` |
| DETALLE_PEDIDO | `importe` | `importe_pactado` |
| DETALLE_PEDIDO | `costo_est` | `costo_estimado` |
| DETALLE_PEDIDO | `costo_real` | `costo_real_consolidado` |
| ASIGNACION_ETAPA | `fec_inicio` | `fecha_inicio` |
| ASIGNACION_ETAPA | `fec_fin` | `fecha_fin` |
| VERSION_DISENO | `fec_crea` | `fecha_creacion` |
| SOLICITUD_CAMBIO | `fec_solicitud` | `fecha_solicitud` |
| APROBACION_DISENO | `id_emp_reg` | `id_empleado_registro` |
| APROBACION_DISENO | `fec_aprobacion` | `fecha_aprobacion` |
| ESCALA_PRECIO | `cant_min` | `cantidad_minima` |
| ESCALA_PRECIO | `cant_max` | `cantidad_maxima` |
| ESCALA_PRECIO | `precio_mayorista` | `precio_unitario_mayorista` |
| COMPOSICION_PRODUCTO | `cant_estandar` | `cantidad_estandar` |
| PROMOCION | `cant_req` | `cantidad_requerida` |
| PROMOCION | `fec_inicio` | `fecha_inicio` |
| PROMOCION | `fec_fin` | `fecha_fin` |
| REGISTRO_AUDITORIA | `fec_hora` | `fecha_hora` |
| ENVIO | `fec_entrega_real` | `fecha_entrega_real` |
| HITO_PAGO | `fec_venc` | `fecha_vencimiento` |
| TRANSACCION | `id_emp_verif` | `id_empleado_verificador` |
| TRANSACCION | `id_tx_comp` | `id_transaccion_compensada` |
| TRANSACCION | `fec_hora` | `fecha_hora` |
| TRANSACCION | `monto` | `monto_con_signo` |
| CANCELACION | `id_emp_autoriza` | `id_empleado_autoriza` |
| CANCELACION | `fec_hora` | `fecha_hora` |
| REEMBOLSO | `fec_solicitud` | `fecha_solicitud` |
| COMPRA | `fec_compra` | `fecha_compra` |
| DETALLE_COMPRA | `cant_comprada` | `cantidad_comprada` |
| DETALLE_COMPRA | `costo_unit_compra` | `costo_unitario_compra` |
| MOVIMIENTO_INVENTARIO | `fec_hora` | `fecha_hora` |
| MOVIMIENTO_INVENTARIO | `costo_unit` | `costo_unitario_aplicado` |
| RESERVA_INVENTARIO | `cant_reservada` | `cantidad_reservada` |
| RESERVA_INVENTARIO | `cant_pendiente` | `cantidad_pendiente` |
| RESERVA_INVENTARIO | `fec_reserva` | `fecha_reserva` |
| RESERVA_INVENTARIO | `fec_liberacion` | `fecha_liberacion` |
| PERDIDA | `id_emp_reporta` | `id_empleado_reporta` |
| PERDIDA | `fec_hora` | `fecha_hora` |
| DETALLE_PERDIDA | `cant_perdida` | `cantidad_perdida` |
| DETALLE_PERDIDA | `costo_unit_hist` | `costo_unitario_historico` |

Dos comentarios del SQL no deben convertirse en renombres: el XML conserva
`PROVEEDOR.correo` y `DETALLE_COMPRA.importe`, aunque los comentarios sugieren
`correo_electronico` e `importe_pactado`. Siguiendo el XML, se mantienen
`correo` e `importe`.

## 4. Columnas que aparecen solo en SQL Server

| Columna | Evidencia de negocio | Resolución propuesta | Aprobación |
|---|---|---|---|
| `PEDIDO.total_pedido` | Las reglas maestras ordenan mantener este total materializado consistente desde el backend. | Conservar como `numeric(19,2) NOT NULL`, calculado dentro de la transacción del pedido. | Ya respaldada por regla explícita |
| `ARTICULO_INVENTARIABLE.existencia_actual` | Las reglas maestras ordenan conservarlo y distinguir existencia física de reserva y disponible. | Conservar como `numeric(18,3) NOT NULL`; modificarlo solo junto con un movimiento inventariable. | Ya respaldada por regla explícita |
| `TRANSACCION.clave_idem` | Se exigen identificadores de idempotencia para operaciones repetibles. | Conservar como `uuid NOT NULL UNIQUE`. | Ya respaldada por regla explícita |
| `DETALLE_PEDIDO.modo_precio` | Permite reconstruir si el precio fue detalle, mayorista, promoción o cotización. | Conservar con CHECK; revisar los valores definitivos. | Requiere aprobar valores del catálogo de estados |
| `DETALLE_PEDIDO.id_promocion` | Permite atribuir el descuento aplicado y reportar promociones utilizadas. | Conservar nullable con FK `ON DELETE NO ACTION`, sujeto a la decisión detallada en §5. | **Requiere aprobación** |
| `PROMOCION.valor_beneficio` | El cálculo no puede derivarse de la descripción textual `beneficio`; los seeds usan 170.00 y 10.00. | Conservar un valor numérico, pero resolver el significado de `beneficio` y `valor_beneficio`. | **Requiere aprobación** |
| `PROMOCION.estado` | Se necesita activar/desactivar sin borrar promociones históricas. | Conservar con estado controlado. | Requiere aprobar valores definitivos |

## 5. FK 64: detalle de pedido a promoción

### Evidencia

- `DETALLE_PEDIDO.id_promocion` **no está presente** en la tabla relacional del
  XML ni existe una arista visual entre `DETALLE_PEDIDO` y `PROMOCION`.
- El SQL agrega la columna nullable y
  `FK_64_DET_PED_PROMO ... ON DELETE NO ACTION` al final del bloque de relaciones.
- `PROMOCION_VARIANTE` define a qué variantes aplica una promoción, pero no
  registra cuál promoción fue realmente aplicada a una venta.
- Las reglas exigen conservar precios y descuentos pactados, evitar promociones
  incompatibles y reportar promociones más utilizadas.

### Análisis

La FK es coherente para trazar **una promoción principal por línea**. Su
nulabilidad representa líneas sin promoción y `NO ACTION` preserva historia. La
FK por sí sola no garantiza que la promoción corresponda a la variante, esté
vigente o sea compatible; esas validaciones pertenecen a FastAPI dentro de la
transacción de creación del pedido.

Eliminarla impediría atribuir de forma relacional la promoción realmente usada.
Conservarla limita el modelo a una promoción por línea. El esquema actual no
puede representar varias promociones simultáneas ni reglas de compatibilidad
promoción-promoción sin ampliar el modelo.

### Propuesta

**Conservar `DETALLE_PEDIDO.id_promocion` como FK nullable a `PROMOCION`, con
`ON DELETE NO ACTION`, y mantener `PROMOCION_VARIANTE` para elegibilidad.** Esta
es una corrección útil del XML, no una consecuencia del conteo 63/64. Requiere
aprobación porque agrega al modelo relacional visual un atributo y una relación.

También debe decidirse si la política oficial permite como máximo una promoción
por línea. Si se permiten varias promociones acumuladas, la FK no basta y sería
necesario revisar el modelo antes de Fase 1.

## 6. Diferencias de unicidad y cardinalidad

Las PK y las marcas UQ coinciden salvo un caso significativo:

- El XML marca `PEDIDO.id_cotizacion` como `[UQ, NULL]`, lo que expresa que una
  cotización puede originar como máximo un pedido.
- El SQL solo crea `UNIQUE (COTIZACION.id_cotizacion, id_cliente)` para soportar
  la FK compuesta que garantiza que pedido y cotización pertenezcan al mismo
  cliente. No declara único `PEDIDO.id_cotizacion`.

Propuesta PostgreSQL: conservar la FK compuesta de pertenencia y añadir
`UNIQUE (id_cotizacion)` en `PEDIDO` (PostgreSQL permite múltiples `NULL` por
defecto). Esto respeta el XML y evita convertir una misma cotización más de una
vez. **Requiere aprobación porque restringe una posibilidad que el SQL actual
permite.**

Las otras marcas UQ del XML (`CUENTA_ACCESO.id_persona`, identificador de
autenticación, códigos, `ENVIO.id_pedido`, `CANCELACION.id_pedido` y
`DETALLE_PERDIDA.id_movimiento`) están representadas en el SQL.

## 7. Nulabilidad

El XML marca explícitamente 32 campos como opcionales y el SQL coincide con
ellos. Hay 38 campos adicionales que el SQL permite nulos aunque el XML no los
marca. Se propone no volverlos obligatorios por omisión: se evalúa su ciclo de
vida y la regla de negocio.

| Tabla y atributo oficial | Propuesta PostgreSQL | Justificación |
|---|---|---|
| PERSONA.`apellidos` | NULL | Personas con un solo nombre o clientes empresa pueden no usar apellidos. |
| PERSONA.`telefono_contacto` | NULL | Puede existir otro canal; FastAPI exigirá al menos un medio cuando el caso de uso lo necesite. |
| CUENTA_ACCESO.`ultimo_acceso` | NULL | Aún no existe antes del primer acceso. |
| COTIZACION.`observaciones` | NULL | Texto complementario. |
| PEDIDO.`nombre_persona_retiro` | NULL | No aplica a envío y puede definirse después. |
| HISTORIAL_PEDIDO.`estado_anterior` | NULL | El primer evento puede no tener estado previo. |
| HISTORIAL_PEDIDO.`motivo` | NULL | No todas las transiciones requieren motivo adicional. |
| DETALLE_COTIZACION.`descripcion_personalizacion` | NULL | Puede cotizarse un producto sin personalización textual. |
| DETALLE_COTIZACION.`descuento_ofrecido` | NOT NULL DEFAULT 0 | Un valor monetario sin descuento es cero; evita tres estados semánticos. |
| DETALLE_PEDIDO.`descuento_aplicado` | NOT NULL DEFAULT 0 | Igual criterio y facilita reconstruir importes históricos. |
| ETAPA_PROCESO.`descripcion` | NULL | El nombre puede ser suficiente. |
| ASIGNACION_ETAPA.`motivo_reasignacion` | NULL | Solo aplica cuando existe reasignación. |
| VERSION_DISENO.`observaciones` | NULL | Complementario al archivo/versionado. |
| SOLICITUD_CAMBIO.`motivo` | NULL | La descripción puede contener el contexto. |
| SOLICITUD_CAMBIO.`decision` | NULL | Pendiente hasta ser resuelta. |
| SOLICITUD_CAMBIO.`cargo_adicional_aprobado` | NULL | Desconocido hasta la decisión. |
| APROBACION_DISENO.`observacion` | NULL | La decisión y medio pueden ser suficientes. |
| CATEGORIA.`descripcion` | NULL | Nombre suficiente. |
| PRODUCTO.`descripcion` | NULL | La información comercial puede cubrir la presentación. |
| VARIANTE_PRODUCTO.`caracteristicas` | NULL | Puede no haber atributos adicionales. |
| PROMOCION.`condiciones` | NULL | Promoción simple sin condiciones adicionales. |
| GASTO.`observaciones` | NULL | Complementario. |
| REGISTRO_AUDITORIA.`valor_anterior` | NULL | No existe en una creación. |
| REGISTRO_AUDITORIA.`valor_nuevo` | NULL | No existe en una eliminación o evento sin cambio de valor. |
| AGENCIA_ENVIO.`telefono` | NULL | Puede no estar disponible; no afecta la referencia histórica. |
| ENVIO.`telefono_receptor` | NULL | Puede obtenerse de la persona; FastAPI lo exigirá cuando la agencia lo requiera. |
| ENVIO.`fecha_programada` | NULL | Aún no existe antes de programar. |
| CANCELACION.`fecha_confirmacion_autenticacion` | NULL | Depende del mecanismo de autorización. |
| REEMBOLSO.`motivo` | NOT NULL propuesto | La trazabilidad financiera requiere una causa explícita. **Requiere aprobación.** |
| REEMBOLSO.`fecha_resolucion` | NULL | Pendiente hasta resolución. |
| PROVEEDOR.`telefono` | NULL | Medio de contacto opcional. |
| PROVEEDOR.`correo` | NULL | Medio de contacto opcional. |
| PROVEEDOR.`direccion` | NULL | Puede no conocerse inicialmente. |
| COMPRA.`numero_documento` | NULL | Puede registrarse borrador antes de recibir documento. |
| MOVIMIENTO_INVENTARIO.`observaciones` | NULL | `motivo` ya es obligatorio. |
| PERDIDA.`id_pedido` | NULL | Las reglas permiten pérdidas generales de almacenamiento. |
| PERDIDA.`descripcion` | NULL | `motivo` ya es obligatorio. |
| DETALLE_PERDIDA.`descripcion_dano` | NULL | El encabezado puede describir el incidente. |

Las tres propuestas que vuelven un campo obligatorio tienen justificación
específica; el resto conserva la opcionalidad del SQL para no imponer datos que
no existen en todos los estados del proceso.

## 8. Tipos con diferencias semánticas

| Atributo | XML/MERE | SQL Server | Propuesta PostgreSQL |
|---|---|---|---|
| ASIGNACION_ROL.`fecha_asignacion` | Texto | `datetime2` | `timestamptz`; representa un instante |
| PEDIDO.`vencimiento_pago` | Texto | `datetime2` | `timestamptz`; se compara con la ventana de 24 horas |
| ARTICULO_INVENTARIABLE.`existencia_minima` | Texto | `decimal(18,3)` | `numeric(18,3)` |
| PROMOCION.`beneficio` | Dinero | `varchar(255)` | Conflicto pendiente: descripción textual frente a valor calculable |
| GASTO.`fecha` | Texto | `datetime2` | `timestamptz` para preservar la precisión encontrada |
| RESERVA_INVENTARIO cantidades | Entero | `decimal(18,3)` | `numeric(18,3)` porque las unidades incluyen ml, g, m y m² |
| MOVIMIENTO_INVENTARIO.`cantidad` | Entero | `decimal(18,3)` | `numeric(18,3)` por la misma razón |

Para `PROMOCION`, la propuesta es conservar `beneficio` como descripción y
`valor_beneficio numeric(19,2)` como operando, con un CHECK dependiente de
`tipo`. Esto representa los seeds y permite cálculos, pero modifica el modelo
visual y requiere aprobación. También debe definirse si un porcentaje puede
tener más de dos decimales y cuáles son sus límites.

Todos los instantes operativos se almacenarán como `timestamptz` en UTC y se
mostrarán en `America/Managua`. Los importes usarán `numeric`, nunca `float`.

## 9. Correspondencia de reglas con las 41 tablas

| Área | Correspondencia existente | Brecha o condición no respaldada |
|---|---|---|
| Invitados | PERSONA, CLIENTE, PEDIDO, DETALLE_PEDIDO y token de seguimiento | No hay credencial a nivel de CLIENTE sombra; debe definirse si el token por pedido basta para consultar historial. Falta fijar exactamente qué estados cuentan como activos. |
| Registrados | CLIENTE, CUENTA_ACCESO, PEDIDO | El límite de dos `PENDIENTE_PAGO` vive en FastAPI con bloqueo; no requiere nueva tabla. |
| Anticipos y pagos | HITO_PAGO, TRANSACCION, REEMBOLSO, CANCELACION | El 50 % “normal” no define excepciones ni regla exacta de redondeo. `clave_idem` debe aprobarse como adición del SQL. |
| Inventario | ARTICULO_INVENTARIABLE, COMPOSICION_PRODUCTO, RESERVA_INVENTARIO, MOVIMIENTO_INVENTARIO | La reserva y sobreventa requieren transacción/bloqueo. `existencia_actual` está respaldada por regla explícita aunque falta en XML. |
| Promociones | PROMOCION, PROMOCION_VARIANTE, DETALLE_PEDIDO | El XML no modela valor calculable, estado ni promoción aplicada. No existe representación de varias promociones compatibles. |
| Diseño | VERSION_DISENO, APROBACION_DISENO, SOLICITUD_CAMBIO | La FK compuesta liga aprobación a versión exacta. Debe definirse si puede haber varias decisiones sobre la misma versión. |
| Producción | ETAPA_PROCESO, ASIGNACION_ETAPA, HISTORIAL_PEDIDO, PEDIDO | Las transiciones y aprobación previa son reglas FastAPI. Falta catálogo definitivo de transiciones. |
| Pérdidas | PERDIDA, DETALLE_PERDIDA, MOVIMIENTO_INVENTARIO | La FK única a movimiento evita doble descuento. No hay catálogo exacto para antes/durante/después ni tipos de incidente. |
| Auditoría | REGISTRO_AUDITORIA | Solo relaciona empleado; las acciones de cliente o sistema no tienen actor relacional. Se recomienda reemplazar `id_empleado` por `id_persona_actor NULL` con FK a PERSONA; `NULL` más `origen_accion='SISTEMA'` representaría procesos automáticos. Requiere aprobación. |

## 10. Separación conceptual de la fuente SQL Server

La fuente original permanecerá intacta. La futura conversión se dividirá así:

- **DDL:** `supabase/migrations/`, ordenado por tablas, restricciones, índices y
  políticas RLS.
- **Seeds:** `database/seeds/`, ficticios, idempotentes y bloqueados en producción.
- **Consultas académicas:** `database/queries/`, reescritas para PostgreSQL y
  validadas de forma independiente.

Los diagnósticos `sys.*`, `IDENTITY_INSERT`, `GO`, `TOP`, corchetes y consultas
con errores no pasarán a una migración.

## 11. Plan definitivo de migración condicionado

Tras aprobar las decisiones semánticas:

1. congelar un diccionario de 41 tablas con nombres completos y nulabilidad;
2. convertir identidades a `GENERATED BY DEFAULT AS IDENTITY` y UUID existentes
   a `uuid` con `gen_random_uuid()`;
3. convertir fechas operativas a `timestamptz`, texto largo a `text`, dinero a
   `numeric(19,2)` y cantidades a `numeric(18,3)`;
4. crear PK, UQ, CHECK y las 63 o 64 FK aprobadas con nombres PostgreSQL menores
   de 63 bytes;
5. conservar `ON DELETE NO ACTION` para historia y revisar únicamente las cinco
   cascadas de tablas de enlace/configuración;
6. implementar exclusión de rangos o validación transaccional para escalas sin
   superposición;
7. crear índices a partir de consultas reales y no copiar automáticamente los 46;
8. diseñar RLS por identidad y propiedad antes de exponer tablas;
9. aplicar desde cero en PostgreSQL real, ejecutar pruebas estructurales y repetir;
10. convertir seeds y consultas fuera del DDL.

## 12. Decisiones necesarias antes de Fase 1

1. Aprobar o rechazar la FK nullable
   `DETALLE_PEDIDO.id_promocion → PROMOCION` y confirmar si se permite como
   máximo una promoción por línea.
2. Aprobar que una cotización solo pueda convertirse en un pedido mediante
   `UNIQUE (PEDIDO.id_cotizacion)`.
3. Resolver `PROMOCION.beneficio`: descripción textual más
   `valor_beneficio numeric`, o una representación distinta; definir límites de
   porcentajes y combinaciones.
4. Aprobar los campos solo-SQL `modo_precio`, `estado` de promoción y sus valores
   definitivos.
5. Aprobar o rechazar el reemplazo de `REGISTRO_AUDITORIA.id_empleado` por
   `id_persona_actor NULL` con FK a `PERSONA`; para procesos automáticos el actor
   sería `NULL` y `origen_accion` identificaría `SISTEMA`.
6. Aprobar la nulabilidad propuesta: descuentos de cotización y pedido como
   `NOT NULL DEFAULT 0`, y `REEMBOLSO.motivo` como `NOT NULL`.
7. Definir estados activos del invitado, política exacta de expiración,
   excepciones/redondeo del anticipo y catálogos de pérdidas/transiciones.

Estos conflictos cambian significado, integridad o trazabilidad. La Fase 1 no
debe comenzar hasta recibir esas decisiones.
