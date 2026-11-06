# Interfaz de demostración

Interfaz responsive en HTML, CSS y JavaScript, servida por FastAPI en `/app/`.
Usa `fetch` contra `/api/v1`, conserva el token de Supabase sólo en
`sessionStorage` y no contiene reglas comerciales, identidades simuladas ni
credenciales privilegiadas.

Incluye catálogo, registro/inicio de sesión, cotizaciones, pedidos y reporte de
pagos para clientes. El panel de empleado consulta pedidos, cotizaciones,
inventario, compras, proveedores, pérdidas y reportes, y permite ejecutar las
decisiones esenciales autorizadas por el backend.

La guía de uso y demostración está en
`docs/guias/demostracion-final-bd.md`.
