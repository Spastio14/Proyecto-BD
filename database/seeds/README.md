# Seeds

`001_demo.sql` contiene datos totalmente ficticios para desarrollo y pruebas.
Está separado del DDL, usa identidades estables, `ON CONFLICT DO NOTHING` y
reajusta las secuencias al finalizar. Cubre las 41 tablas para detectar problemas
de orden o relaciones.

El runner `../tests/run.sh` lo aplica únicamente a su base efímera. No debe
ejecutarse en producción ni contra un proyecto Supabase remoto.
