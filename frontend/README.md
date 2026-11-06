# Interfaz de demostración

Interfaz responsive en HTML, CSS y JavaScript, servida por FastAPI en `/app/`.
Usa `fetch` contra `/api/v1`, conserva el token de Supabase sólo en
`sessionStorage` y no contiene reglas comerciales, identidades simuladas ni
credenciales privilegiadas.

La página pública ofrece catálogo, inicio de sesión y registro exclusivo de
clientes. Después del login consulta `/api/v1/auth/me` y navega al dashboard
determinado por roles y permisos efectivos de PostgreSQL:

- `/app/cliente/`
- `/app/admin/`
- `/app/contabilidad/`
- `/app/ventas/`
- `/app/produccion/`

Los menús se adaptan al perfil para mejorar la experiencia, pero la autorización
real permanece en cada servicio FastAPI. La clave privada de Supabase nunca se
envía al navegador.

La guía de uso y demostración está en
`docs/guias/fase-4-2-empleados-roles.md`.
