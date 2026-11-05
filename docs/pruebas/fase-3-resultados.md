# Resultados de pruebas — Fase 3

Fecha de ejecución: 2026-11-05 (UTC). Rama:
`feat/fase-3-supabase`.

## Entorno comprobado

- PostgreSQL local desechable: 17.11, imagen `postgres:17-alpine`.
- Python: 3.12.14.
- Pytest: 8.4.2.
- Supabase CLI temporal: 3.0.0 mediante `npx`; `status` leyó
  `supabase/config.toml` y confirmó que no existe un stack local iniciado.
- Supabase CLI enlazado/remoto: no ejecutado; no hay token, contraseña ni
  conectividad permitida al proyecto en este entorno.
- Proyecto Supabase remoto: no contactado ni modificado.

## Resultados ejecutados

```text
./database/tests/run.sh
OK: 41 tablas, 64 FK, nombres conciliados, integridad y RLS verificados.
OK: dos reconstrucciones limpias y pruebas PostgreSQL/RLS completadas.

./backend/tests/run.sh
77 casos recopilados
75 passed, 2 skipped, 1 warning
```

Uvicorn inició y `/api/v1/health` respondió contra PostgreSQL antes de Pytest.
Ruff comprobó y formateó `app` y `tests` sin errores.

Los 25 casos nuevos ejecutados demostraron:

1. JWT ES256 válido con firma, audiencia y emisor correctos;
2. rechazo de firma inválida;
3. rechazo de token vencido;
4. rechazo de otro proyecto;
5. resolución del `sub` a cliente activo;
6. rechazo de una cuenta no vinculada;
7. imposibilidad de convertir un claim de rol en identidad de empleado;
8. credencial válida de invitado;
9. rechazo de una credencial invitada alterada;
10. registro y vínculo Auth–`cuenta_acceso`;
11. compensación del usuario externo ante conflicto local;
12. obligación de TLS en PostgreSQL remoto;
13. compatibilidad del transaction pooler sin prepared statements;
14. carga de diseño y referencia a versión privada;
15. rechazo de MIME no permitido antes de cargar;
16. borrado compensatorio si falla el vínculo del diseño;
17. referencia estructural del comprobante a la transacción;
18. prohibición y compensación de reemplazo silencioso;
19. verificación de propiedad antes de una URL firmada;
20. denegación de tablas privadas al rol `authenticated`.
21. rechazo de una cuenta local suspendida;
22. resolución de empleado y permiso exclusivamente desde PostgreSQL;
23. rechazo de una carga de diseño ajena antes de contactar Storage;
24. privacidad del comprobante frente a otro cliente;
25. plazo acotado solicitado al generar una URL firmada.

Los dos casos omitidos están marcados `remote` y sólo se habilitan con
`RUN_SUPABASE_REMOTE_TESTS=1`: comprobar PostgreSQL 17/esquema remoto y comparar
el historial de migraciones enlazado. La omisión es intencional; no se presenta
como éxito.

## Cobertura de amenazas

| Riesgo | Evidencia |
|---|---|
| JWT inventado, vencido o de otro proyecto | casos 51–54 |
| cuenta inexistente/inactiva o rol declarado por cliente | casos 55–57 |
| suplantación por ID de invitado | casos 58–59 y ausencia de endpoint de ID |
| usuario Auth huérfano | caso 61 |
| credenciales PostgreSQL remotas sin TLS | casos 62–63 |
| archivo ejecutable, grande o de extensión incoherente | validaciones de servicio; caso 65 para MIME |
| objeto huérfano por fallo local | caso 66 |
| comprobante no relacionado o sobrescrito | casos 67–68 y CHECK SQL |
| URL firmada para otro cliente | caso 69 |
| acceso directo a datos privados | caso 70 y runner RLS |

## Pendiente remoto

No pudo ejecutarse `scripts/supabase/preflight.sh` porque este entorno no tiene
un enlace autenticado, secretos ni conectividad permitida a los dominios
Supabase. El script admite CLI instalado o `npx`, verifica el proyecto mediante
la API, consulta PostgreSQL con `--read-only`, ejecuta
`migration list --remote`, ejecuta `db push --remote --dry-run --skip-vault` y
comprueba los metadatos públicos JWKS sin imprimir material de clave. Sólo después
de revisar esos resultados se puede solicitar autorización para aplicar las
migraciones.

El warning de Starlette sobre una futura transición de `TestClient` a `httpx2`
proviene de una dependencia y no afectó la ejecución.
