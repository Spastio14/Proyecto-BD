# Fase 4.5.2 — auditoría de unidades y datos de demostración

La auditoría fue local y sobre fuentes versionadas. No se consultó ni modificó
Supabase remoto.

## Botella deportiva y unidades

La fuente SQL Server encontrada modela la variante `BOTELLA-SPORT` con la
presentación comercial “600 ml”, pero el artículo inventariable
`INS-BOTELLA` usa correctamente `UNIDAD`. La tinta `INS-TINTA` usa `ML`. La
capacidad de una botella pertenece a la variante o presentación comercial y no
debe utilizarse como unidad de existencia.

Si un ambiente contiene una botella con unidad `ML`, la corrección propuesta
requiere primero identificar el artículo, sus composiciones, compras, reservas,
movimientos y pérdidas. Después de confirmar que cada existencia representa una
botella, se puede cambiar sólo la unidad vigente a `UNIDAD` mediante una
migración de datos autorizada. No se deben multiplicar existencias ni reescribir
movimientos históricos. Si las cantidades representan volumen de material, el
cambio sería semánticamente incorrecto.

Esta decisión queda pendiente de revisar el registro real y su historial. No se
incluye una corrección automática.

## Importes y existencias extremos

Los seeds canónicos del repositorio contienen escenarios académicos y deben
permanecer separados de los datos comerciales. La suite crea PostgreSQL desde
una plantilla local y carga `database/seeds/001_demo.sql` y
`003_roles_permisos_fase_4_2.sql`; no ejecuta estos archivos en Supabase.

Los valores extremos informados en el ambiente remoto no se pueden atribuir a
una fuente definitiva sólo con el repositorio actual. La propuesta controlada
es:

1. conservar el proyecto actual como desarrollo/pruebas hasta clasificar los
   registros;
2. usar un proyecto o base distinta para producción;
3. etiquetar el origen de futuras cargas de demostración;
4. obtener un inventario de filas extremas mediante consultas de sólo lectura;
5. presentar una lista de correcciones por clave antes de cualquier escritura;
6. no borrar pedidos, movimientos ni auditoría para “limpiar” reportes.

No se realizó limpieza, conversión ni actualización remota.
