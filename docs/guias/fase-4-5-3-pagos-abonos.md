# Fase 4.5.3 — pagos, abonos y caja

## Modelo financiero

`TRANSACCION` sigue siendo la única representación del dinero reportado o
recibido. `APLICACION_TRANSACCION_HITO` distribuye ese importe entre ANTICIPO y
SALDO. La suma de aplicaciones de una transacción debe coincidir con su importe,
pero los reportes de ingresos suman `TRANSACCION` una sola vez.

La migración incremental añade tres tablas justificadas:

- `APLICACION_TRANSACCION_HITO`: relación normalizada muchos a muchos con el
  importe aplicado a cada hito.
- `CAJA`: apertura y cierre de la caja activa.
- `MOVIMIENTO_CAJA`: ingreso en efectivo, folio, empleado y transacción asociada.

Los pagos históricos conservan método, importe y estado. La migración crea una
aplicación equivalente para cada pago histórico que ya tenía `numero_hito`. No
reescribe importes ni elimina transacciones.

## Reglas operativas

- Solo se crean pagos nuevos por TRANSFERENCIA o EFECTIVO.
- Una transferencia exige banco emisor, referencia e importe positivo.
- La combinación normalizada banco emisor + referencia se protege contra
  duplicados; la misma referencia puede existir en bancos diferentes.
- Los pagos pendientes reservan capacidad de reporte, pero no cuentan como
  dinero recibido ni habilitan inventario o producción.
- Un rechazo libera el importe para un nuevo intento.
- La reserva se crea una sola vez cuando el anticipo verificado alcanza el 50 %.
- La modalidad TOTAL distribuye una operación entre anticipo y saldo cuando
  corresponde.
- El efectivo solo se registra por un empleado con `PAGO_VERIFICAR` y una caja
  abierta. El servidor genera el folio.
- El portal nunca confirma efectivo: únicamente muestra instrucciones de pago
  presencial.

## WhatsApp

Configurar `BUSINESS_WHATSAPP_NUMBER` con el número internacional en dígitos,
sin `+`, espacios ni guiones. Ejemplo de formato: `505XXXXXXXX`.

El frontend prepara el mensaje y abre `wa.me`; no envía mensajes ni archivos.
El cliente debe adjuntar manualmente la captura del comprobante. WhatsApp nunca
verifica ni autoriza el pago.

## Aplicación posterior en Supabase

1. Actualizar la rama fusionada y autenticar Supabase CLI sin exponer tokens.
2. Verificar el proyecto enlazado.
3. Ejecutar `supabase migration list`.
4. Ejecutar `supabase db push --dry-run` y confirmar que solo aparece
   `202611070004_payment_allocations_cash.sql`.
5. Ejecutar el diagnóstico de solo lectura para los pedidos señalados.
6. Revisar el backfill de aplicaciones y los totales sin duplicación.
7. Solicitar autorización independiente antes de ejecutar `supabase db push`.

No ejecutar seeds académicos ni `db reset` sobre el proyecto remoto.
