# Fase 4.5 — revisión con Web Interface Guidelines

Revisión realizada el 7 de noviembre de 2026 con la versión vigente de
`vercel-labs/web-interface-guidelines`. Los hallazgos se corrigieron antes de la
regresión.

## `frontend/index.html`

- `frontend/index.html:13` — enlace para saltar al contenido incorporado.
- `frontend/index.html:39` — imagen crítica con `alt`, dimensiones explícitas y
  `fetchpriority="high"`.
- `frontend/index.html:68` — correo con tipo, autocompletado y corrector
  ortográfico desactivado.
- `frontend/index.html:106` — avisos asíncronos expuestos con `aria-live`.

## `frontend/dashboard.js`

- `frontend/dashboard.js:22` — controles dinámicos reciben autocompletado
  explícito y correos sin corrector ortográfico.
- `frontend/dashboard.js:29` — tablas desplazables con nombre accesible,
  navegación por teclado y encabezados `scope="col"`.
- `frontend/dashboard.js:80` — estado vacío útil cuando no hay registros.
- `frontend/dashboard.js:88` — moneda presentada con `Intl.NumberFormat`.
- `frontend/dashboard.js:89` — el resumen cliente prioriza el pedido activo y
  ofrece una acción con botón semántico.

## `frontend/styles.css`

- `frontend/styles.css:35` — áreas interactivas optimizadas para toque sin
  bloquear el zoom del navegador.
- `frontend/styles.css:50` — foco visible global y específico de formularios.
- `frontend/styles.css:190` — tablas contienen datos largos y mantienen
  desplazamiento propio.
- `frontend/styles.css:231` — breakpoints del escaparate, portal y paneles sin
  desbordamiento horizontal del documento.
- `frontend/styles.css:287` — movimiento reducido respetado.

## Portales por rol

- `frontend/cliente/index.html:11` — enlace de salto, navegación con nombre y
  región principal identificada.
- `frontend/admin/index.html:11` — shell administrativo semántico y separado del
  portal comercial.
- `frontend/ventas/index.html:11` — misma estructura accesible con prioridad de
  ventas.
- `frontend/contabilidad/index.html:11` — misma estructura accesible con
  prioridad financiera.
- `frontend/produccion/index.html:11` — misma estructura accesible con prioridad
  de diseños y producción.
- `frontend/activar-empleado/index.html:11` — visita privada con contenido
  principal, estados anunciados y campos de contraseña identificados.

## Comprobación en navegador

Se cargaron escaparate, cliente y administración con respuestas API simuladas,
sin conexión a Supabase, en 1440 × 1000 px y 390 × 844 px. Los 6 escenarios
obtuvieron:

- ancho del documento igual al viewport;
- 0 controles sin etiqueta;
- 0 imágenes sin texto alternativo;
- 0 enlaces o botones sin nombre accesible;
- foco visible después de navegar con Tab.
