# Auditoría de fuentes — Fase 0

Fecha de auditoría: 4 de noviembre de 2026.

> Esta auditoría fue seguida por una comparación exhaustiva. La resolución y
> los conteos corregidos están en
> [`conciliacion-xml-sqlserver.md`](conciliacion-xml-sqlserver.md).

## 1. Archivos e historial encontrados

El repositorio tiene dos commits en la rama remota `master`:

| Commit | Descripción | Contenido relevante |
|---|---|---|
| `bc1f500514a8db01bf9218d0a7759c1eb6972749` | `README` | `README.md` vacío |
| `6611604622190a2c945c7003a1a0407e92deeffe` | `documentos de referencia` | XML de diagrams.net y SQL Server |

La copia publicada inicialmente estaba en el primer commit. Durante la auditoría
se consultó el remoto y se avanzó el checkout de forma lineal al segundo commit,
sin reescribir historial ni sobrescribir cambios locales.

Archivos de referencia encontrados:

| Archivo | Evidencia |
|---|---|
| `docs/S2R_BD.drawio.xml` | XML editable; declara tres páginas, contiene un diagrama y un modelo relacional visual de 41 tablas. El propio lienzo anuncia 63 relaciones. |
| `docs/copia - Sublimacion2R.sql` | Script T-SQL de 1,736 líneas: 41 `CREATE TABLE`, 64 FK, 46 índices, datos de demostración y consultas preliminares. |

No se encontraron otros documentos, UML independientes, migraciones, código,
manifiestos de dependencias, pruebas ni un archivo identificado como “V3.0”.

## 2. Fuente de verdad identificada

Las dos fuentes coinciden en los nombres de las 41 tablas exigidas. El XML
contiene los nombres completos de los atributos y el SQL contiene tipos,
restricciones, claves, índices y seeds. Ninguno está marcado en Git como versión
aprobada definitiva.

Por tanto, el criterio provisional es:

1. Las reglas explícitas entregadas por el propietario gobiernan el comportamiento.
2. La lista de 41 tablas y los nombres completos del modelo relacional visual
   gobiernan la identidad conceptual.
3. El script T-SQL aporta una especificación técnica provisional que debe
   reconciliarse con el XML antes de convertirse.
4. Los datos y consultas del final del script son material preliminar, no parte
   de la definición canónica.

La base PostgreSQL no puede declararse definitiva hasta confirmar las preguntas
abiertas de esta auditoría.

## 3. Inconsistencias y brechas

### Entre el XML y el SQL

- El encabezado del modelo visual indica **63 relaciones**, mientras el SQL crea
  **64 claves foráneas**. La FK adicional aparente es
  `FK_64_DET_PED_PROMO`, de `DETALLE_PEDIDO.id_promocion` a `PROMOCION`;
  `id_promocion` no aparece como atributo de `DETALLE_PEDIDO` en el modelo
  relacional visual.
- El XML usa nombres completos y el SQL abrevia 57 ocurrencias verificadas. La
  cifra preliminar de 48 fue corregida mediante comparación campo por campo. Ejemplos:
  `telefono_contacto → tel`, `identificador_autenticacion → auth_uid`,
  `fecha_creacion → fec_crea`, `precio_unitario_aplicado → precio_unit` y
  `cantidad_reservada → cant_reservada`. Debe decidirse qué nombres son oficiales
  para PostgreSQL y la API.
- El XML marca algunos atributos opcionales de forma distinta al SQL. Por
  ejemplo, `CUENTA_ACCESO.ultimo_acceso` no muestra `[NULL]` en el diagrama,
  mientras el SQL lo permite. Se requiere una comparación campo por campo antes
  de migrar.
- El XML declara `pages="3"`, pero el archivo contiene un único elemento
  `<diagram>`. Esto no impide leerlo, aunque sugiere que la exportación o el
  metadato de páginas puede estar desactualizado.

### Dentro del script T-SQL

- El nombre del archivo no identifica una versión V3.0 ni aprobación formal.
- Mezcla DDL, datos de demostración, diagnóstico y consultas académicas. En
  PostgreSQL estos elementos deben separarse en migraciones, seeds y consultas.
- Usa sintaxis exclusiva de SQL Server: `GO`, `[dbo]`, `IDENTITY`,
  `DATETIME2`, `UNIQUEIDENTIFIER`, `NEWID()`, `VARCHAR(MAX)`,
  `IDENTITY_INSERT`, catálogos `sys.*`, concatenación con `+` y `TOP 1`.
- Algunas consultas finales no compilan o no representan los estados del
  esquema: hay un `FROM PERSONA AS P ON ...` sin `JOIN`, alias no definidos,
  sentencias sin terminador y una consulta del producto más vendido que busca
  `PRODUCCION`, aunque el CHECK define `EN_PRODUCCION`.
- El script no contiene vistas, triggers ni procedimientos. Esto coincide con el
  principio de mantener la lógica comercial en el backend, pero aún faltan
  migraciones y políticas RLS.
- Hay cinco cascadas en relaciones de catálogo o enlace. Deben revisarse una por
  una; no se aceptarán cascadas sobre historia financiera, auditoría u operaciones.
- Los CHECK de columnas anulables no rechazan `NULL` por sí solos. Debe
  confirmarse si descuentos, costos consolidados y montos aprobados pueden ser
  nulos o deben usar cero explícito.
- El correo se valida con un patrón `LIKE` muy débil. La forma se validará en
  Pydantic y la base conservará solo invariantes útiles; no se intentará codificar
  toda la especificación de correo en un CHECK.
- Los seeds fijan fechas, IDs y totales dentro del mismo archivo. Deben volverse
  reproducibles e idempotentes y quedar claramente aislados de producción.

### Reglas que no quedan garantizadas solo por el esquema

- Máximo de cinco unidades por pedido invitado y un pedido invitado activo.
- Máximo de dos pedidos `PENDIENTE_PAGO` para clientes registrados.
- Protección verificable del historial de una cuenta sombra invitada.
- Ventana de pago de 24 horas y expiración idempotente.
- Confirmación del 50 % antes de reservar, sin sobreventa concurrente.
- No iniciar producción sin aprobación de la versión exacta del diseño.
- No superponer escalas de precio ni promociones incompatibles.
- Append-only financiero, compensaciones y claves de idempotencia.
- Cálculo de utilidad sin duplicar costos ni pérdidas.
- Autorización por rol, propiedad de recursos y políticas RLS.

Estas reglas pertenecen principalmente a servicios FastAPI, con transacciones y
bloqueos PostgreSQL donde exista riesgo de carrera.

## 4. Criterio provisional de resolución

- Conservar ambas fuentes originales sin cambios.
- Usar nombres completos del modelo relacional como candidatos preferidos, pero
  no renombrar columnas hasta obtener aprobación explícita.
- Mantener la relación opcional entre detalle de pedido y promoción como decisión
  pendiente, porque el SQL y el XML discrepan.
- Convertir tipos y sintaxis, no el significado del modelo.
- Separar DDL, seeds y consultas en destinos distintos.
- Mantener las identidades `INT` existentes mientras no exista evidencia de que
  el modelo aprobado exige UUID v4 para una entidad concreta. Los UUID ya
  presentes (`token_seguimiento`, `clave_idem`) se convertirán a `uuid`.

## 5. Preguntas que requieren decisión del propietario

1. ¿El commit `6611604` contiene el script aprobado V3.0 o existe otra versión?
2. ¿Los nombres oficiales de columnas son los completos del XML o los abreviados
   del T-SQL?
3. ¿Se aprueba `DETALLE_PEDIDO.id_promocion` y la relación FK 64, aunque no figure
   en la tabla visual?
4. ¿Qué campos están realmente permitidos como `NULL`, especialmente
   `CUENTA_ACCESO.ultimo_acceso`, descuentos y costos reales?
5. ¿Qué entidades, además de los tokens existentes, deben usar UUID v4?
6. ¿Cuál es la política exacta al expirar un pedido y qué reservas o pagos deben
   preservarse?
7. ¿Cómo se autentica de forma verificable a un invitado para consultar su pedido
   sin confiar en un ID del navegador?
8. ¿Qué combinaciones de promociones se permiten y cómo se resuelven empates?

Estas decisiones bloquean la declaración de un esquema definitivo, pero no el
diseño de la infraestructura de pruebas ni la preparación técnica de la Fase 1.
