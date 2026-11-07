# Fase 4.5 — dirección visual de Sublimación Doble R

## Auditoría de la interfaz anterior

La interfaz cumple los flujos funcionales, pero no diferencia con claridad la
experiencia comercial de la operación interna. El portal cliente reutiliza el
mismo shell del personal, el catálogo presenta texto sin producto protagonista
y la navegación móvil oculta enlaces sin ofrecer una alternativa equivalente.

La identidad anterior combina crema, Georgia, terracota, etiquetas en
mayúsculas y una cuadrícula de tarjetas redondeadas idénticas. Ese conjunto se
percibe como una plantilla común y resta personalidad al negocio. En la parte
administrativa, los indicadores, formularios y tablas compiten por atención; en
la pública aparece información técnica de PostgreSQL y FastAPI que no ayuda a
comprar ni a comprender el proceso de personalización.

## Concepto: taller editorial de personalización

Doble R se presenta como un taller que convierte ideas en objetos cuidados. La
firma visual toma del proceso de sublimación la precisión del registro, las
muestras de tinta y la materialidad de cerámica, tela y papel. La expresión es
cálida y comercial sin parecer artesanal improvisada; los paneles internos
heredan la misma tinta y tipografía con una composición más sobria y productiva.

La imagen memorable se concentra en el escaparate de productos y en una pequeña
marca de registro junto al nombre. El resto permanece sereno: sin degradados,
gráficos decorativos, iconos repetitivos ni sombras uniformes en cada bloque.

## Sistema visual

### Color

| Token | Valor | Uso |
|---|---|---|
| Porcelana | `#FAF9F6` | Fondo comercial principal |
| Papel | `#F1EEE9` | Superficie secundaria y filas alternas |
| Blanco | `#FFFFFF` | Formularios, tablas y producto |
| Tinta | `#2B2529` | Texto principal y controles oscuros |
| Ciruela | `#6F274D` | Marca, acciones principales y foco |
| Salvia | `#53695C` | Estados positivos y apoyo operativo |
| Línea | `#DDD7D2` | Separadores que expresan estructura |

Los estados de advertencia y error conservan contraste propio. Ningún estado
depende únicamente del color: siempre incluye texto legible.

### Tipografía

Se utiliza **Onest**, una sans humanista variable, para marca, títulos, texto y
datos. La personalidad procede de escala, peso y ritmo en lugar de combinar una
serif editorial con una sans de plantilla. Los importes y cifras operativas usan
números tabulares. Los párrafos no superan aproximadamente 72 caracteres.

Escala base: 14, 16, 18, 24, 32, 48 y 68 px. Los títulos usan interlineado corto;
los textos y ayudas mantienen entre 1.45 y 1.65.

### Espaciado y forma

La escala es 4, 8, 12, 16, 24, 32, 48 y 64 px. Los controles tienen al menos
44 px de alto. Los radios cambian con la función: 6 px para controles, 10 px
para paneles operativos y 18 px para imágenes de producto. Las tablas usan
líneas horizontales y espacio; no se encierra cada celda.

### Controles y estados

- Acción principal: fondo ciruela, texto blanco y verbo específico.
- Acción secundaria: fondo transparente, borde discreto y texto tinta.
- Acción destructiva: sólo aparece en el contexto que la necesita.
- Foco: anillo exterior de ciruela con separación del control.
- Formularios: etiqueta visible, ayuda debajo y error junto al campo.
- Movimiento: sólo confirma una acción o abre navegación; se respeta
  `prefers-reduced-motion`.

## Estructura

### Escaparate y acceso

```text
┌ marca ───── catálogo · proceso · acceso ───── crear cuenta ┐
├─────────────────────────────────────────────────────────────┤
│ Promesa concreta + dos acciones      fotografía de producto │
│ proceso: elige → personaliza → aprueba → recibe             │
├─────────────────────────────────────────────────────────────┤
│ Catálogo                         filtros y actualización     │
│ [ producto ] [ producto ] [ producto ]                       │
├─────────────────────────────────────────────────────────────┤
│ Acceso existente              registro exclusivo de cliente │
└─────────────────────────────────────────────────────────────┘
```

El contenido se alinea a la izquierda. La fotografía aporta el único gesto
editorial dominante; los productos y acciones conservan una retícula regular.

### Portal cliente

```text
┌ marca ─ catálogo · pedidos · seguimiento ─ perfil · salir ┐
├────────────────────────────────────────────────────────────┤
│ saludo y estado útil                                       │
│ pedido activo o invitación a comprar                       │
├────────────────────────────────────────────────────────────┤
│ productos y acciones comerciales, después historial        │
└────────────────────────────────────────────────────────────┘
```

Usa cabecera de tienda en lugar de barra lateral. En móvil, la navegación es
horizontal y desplazable; nunca desaparece.

### Paneles de personal

```text
┌ marca │ identidad, rol y estado                            ┐
│ menú  ├────────────────────────────────────────────────────┤
│ por   │ título y acción prioritaria                        │
│ rol   │ indicadores en una franja con separadores          │
│       │ tabla principal                                    │
│ salir │ formularios secundarios después del trabajo actual │
└───────┴────────────────────────────────────────────────────┘
```

Administración prioriza resumen y excepciones; Ventas, pedidos y clientes;
Contabilidad, pagos y reportes; Producción, diseños y siguiente operación
permitida. Todos comparten componentes, pero no el mismo orden de información.

## Revisión de singularidad antes de construir

La primera propuesta aún podía caer en el patrón boutique de fondo crema y
acento cálido. Se corrigió eliminando terracota, serif de alto contraste,
etiquetas en mayúsculas y tarjetas repetidas. La identidad queda anclada al
registro de impresión, al color ciruela de las tintas y a fotografías reales de
objetos sublimables. Los paneles administrativos usan separación tipográfica y
líneas funcionales, reservando las superficies elevadas para tareas concretas.

La muestra inicial abarcó el escaparate/portal cliente y el resumen
administrativo. Se comprobó en Chromium a 1440 × 1000 px y 390 × 844 px antes
de extender el sistema a ventas, contabilidad, producción, activación y los
módulos existentes. La validación confirmó que el ancho del documento coincide
con el viewport, que los controles conservan nombre accesible y que la
navegación por teclado muestra foco visible.

## Aplicación por contexto

- **Escaparate:** promesa comercial, fotografía de producto, proceso de compra,
  catálogo y acceso. No expone detalles de implementación al comprador.
- **Cliente:** cabecera horizontal, pedido activo como primera tarea, catálogo,
  compras, pagos y seguimiento con la misma expresión de tienda.
- **Administración:** menú lateral, métricas prioritarias, excepciones y tablas;
  los indicadores secundarios quedan en una sección desplegable.
- **Ventas:** pedidos primero, seguidos de cotizaciones, clientes y pagos.
- **Producción:** diseños y operaciones autorizadas primero, luego pedidos,
  inventario e incidencias.
- **Contabilidad:** resumen financiero, pagos, compras, inventario y reportes.
- **Activación:** página privada y sobria que conserva las comprobaciones de la
  invitación y el establecimiento de contraseña.

La fotografía del escaparate se generó específicamente para Doble R y se guarda
como `frontend/assets/taller-doble-r.webp`. Onest se distribuye localmente bajo
la SIL Open Font License incluida junto al archivo de fuente.
