# Pruebas PostgreSQL

`run.sh` inicia PostgreSQL 17 en Docker, crea dos bases independientes y aplica
en ambas todas las migraciones desde cero. En la primera carga el seed y ejecuta
`001_schema_integrity.sql`.

Las pruebas comprueban los conteos estructurales, las 57 equivalencias de
nombres, restricciones críticas, la FK de promoción y el acceso RLS del catálogo.
También ejecutan una consulta como `anon` y exigen que la lectura de `PERSONA`
sea rechazada.

```bash
./database/tests/run.sh
```

Se puede cambiar la imagen sin editar el script:

```bash
POSTGRES_IMAGE=postgres:17-alpine ./database/tests/run.sh
```
