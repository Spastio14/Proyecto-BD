# Fase 4.4 — invitaciones y activación de empleados

Esta guía complementa `fase-4-4-administracion.md`, que documenta los demás
módulos administrativos de la fase.

## Flujo y estados

Sólo un empleado activo con `EMPLEADO_GESTIONAR` puede iniciar o reenviar una
invitación. El alta crea una `PERSONA`, un `EMPLEADO` en estado `INACTIVO` y una
única asignación de rol. La respuesta `PENDIENTE_ACTIVACION` significa que
Supabase aceptó la solicitud. No confirma que el proveedor haya entregado el
correo.

El panel administrativo muestra estos estados derivados del perfil, la cuenta y
la auditoría:

| Estado | Significado |
|---|---|
| Pendiente de envío | Existe el perfil autorizado, pero todavía no hay identidad Auth vinculada. |
| Solicitud aceptada / pendiente de activación | La identidad Auth está vinculada y el empleado sigue inactivo. |
| Solicitud fallida | Supabase rechazó o no pudo completar el último intento. |
| Activa | El enlace fue verificado, se definió la contraseña y el empleado quedó activo. |
| Suspendida | El perfil laboral o la cuenta de acceso impiden entrar. |

No se infiere que un enlace expiró por el paso del tiempo. Ese mensaje sólo se
muestra cuando Supabase rechaza el enlace como vencido o inválido.

## Reenvío seguro

`POST /api/v1/empleados/{id}/reenviar-invitacion` exige el permiso
`EMPLEADO_GESTIONAR`, bloquea la operación por empleado y aplica un intervalo de
60 segundos entre solicitudes.

- Si el primer intento no creó una identidad Auth, se solicita una invitación
  oficial nueva.
- Si ya existe `CUENTA_ACCESO`, el servidor consulta la identidad por su UUID con
  la API administrativa, exige que UUID y correo coincidan y solicita un enlace
  oficial de recuperación. El frontend acepta enlaces Auth `invite` y `recovery`.
- No se crean otra persona, empleado, cuenta o asignación de rol.
- Un empleado activo, suspendido o con cuenta bloqueada no admite reenvío.
- Un cliente nunca se convierte en empleado y no basta con conocer un correo.
- No se borra ni se reemplaza ningún usuario de Supabase Auth.
- La solicitud, el resultado y el código de error seguro quedan en
  `REGISTRO_AUDITORIA`; no se guardan tokens, claves ni contraseñas.

Aunque una identidad Auth ya pueda emitir un JWT, los endpoints protegidos
rechazan al empleado mientras `EMPLEADO.estado_laboral` sea `INACTIVO`. La
activación sólo ocurre después de validar el JWT, el UUID Auth, el correo, la
invitación administrativa pendiente y el rol activo. Después se establece y
confirma la contraseña, se cambia el estado laboral a `ACTIVO` y `/auth/me`
determina el dashboard del rol.

## Configuración de redirección local

En el entorno del backend:

```dotenv
EMPLOYEE_INVITE_REDIRECT_URL=http://127.0.0.1:8000/app/activar-empleado/
```

En **Supabase Dashboard → Authentication → URL Configuration → Redirect URLs**
se agrega exactamente:

```text
http://127.0.0.1:8000/app/activar-empleado/
```

Esta dirección sólo funciona en la computadora que ejecuta la aplicación. Un
teléfono u otro equipo interpreta `127.0.0.1` como sí mismo y no puede abrir el
servidor de desarrollo.

## HTTPS accesible desde otros dispositivos

Para una demostración sin comprar un dominio puede publicarse temporalmente el
puerto local con un proveedor que entregue una URL HTTPS, por ejemplo Cloudflare
Quick Tunnel, Tailscale Funnel o ngrok. Para cada URL generada:

1. Establecer `EMPLOYEE_INVITE_REDIRECT_URL` con la ruta completa, por ejemplo
   `https://URL-ASIGNADA/app/activar-empleado/`.
2. Agregar esa misma URL exacta a las Redirect URLs permitidas de Supabase.
3. Reiniciar el backend y generar una invitación nueva; los enlaces anteriores
   conservan su redirección original.
4. Retirar la URL temporal de Supabase al terminar la demostración.

Las URL efímeras pueden cambiar al reiniciar el túnel. Para uso continuo se debe
usar una URL HTTPS estable y restringida. Esta fase no cambia la configuración
del proyecto Supabase remoto.

## Activación y recuperación operativa

1. El administrador crea el empleado con el correo y rol correctos.
2. Comprueba en el panel que el estado sea pendiente y comunica al empleado que
   revise su correo, incluido spam.
3. El empleado abre el enlace en el navegador donde completará la activación,
   define y confirma su contraseña.
4. El sistema valida la sesión antes de guardarla, activa el perfil y redirige al
   dashboard correspondiente.
5. Si Supabase informa que el enlace venció o ya se usó, el administrador pulsa
   **Solicitar enlace nuevo**. No debe volver a crear el empleado.
6. Si aparece **Solicitud fallida**, se respeta el intervalo mostrado y se
   reintenta. Un `429` requiere esperar el límite impuesto por Supabase; un `503`
   indica una indisponibilidad temporal.
7. Si la identidad Auth no coincide con el UUID o correo autorizado, se detiene
   el proceso para revisión. No se desvincula ni elimina la identidad.

Para comprobar el flujo en el navegador, abrir
`/app/admin/?view=employees`, crear un empleado de prueba en un proyecto local o
autorizado, revisar el estado pendiente y usar el enlace recibido. Antes de
activar, cualquier endpoint laboral debe responder `403`; después de definir la
contraseña, `/api/v1/auth/me` debe devolver el rol y dashboard esperados.
