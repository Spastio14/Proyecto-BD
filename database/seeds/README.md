# Seeds

`001_demo.sql` contiene datos totalmente ficticios para desarrollo y pruebas.
Está separado del DDL, usa identidades estables, `ON CONFLICT DO NOTHING` y
reajusta las secuencias al finalizar. Cubre las 41 tablas para detectar problemas
de orden o relaciones.

El runner `../tests/run.sh` lo aplica únicamente a su base efímera. No debe
ejecutarse en producción ni contra un proyecto Supabase remoto.

`002_fase_4_1_demo.sql` es opcional y prepara un producto, artículo con 20
unidades y proveedor aislados para la demostración integral. La compra de 30,
el pedido de 5 y las operaciones posteriores se realizan mediante la API para
mostrar las transacciones reales. Este segundo seed tampoco se carga de forma
automática ni debe ejecutarse en Supabase remoto.

`003_roles_permisos_fase_4_2.sql` instala de forma idempotente los perfiles
ADMINISTRADOR, CONTADOR, VENDEDOR y PRODUCCION, junto con permisos separados
para consulta, gestión y autorización. Es DML versionado sobre las tablas
existentes: no agrega una sexta migración ni se aplica remotamente sin la
autorización explícita del propietario.
