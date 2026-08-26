---
sidebar_position: 2
---

# Performance y Escalabilidad Sprint 2

## Objetivo

Implementar medición real de performance (base de datos + request) y habilitar señales operativas de escalabilidad, sin tocar lógica de negocio.

## Alcance técnico implementado

### 1) Instrumentación SQL por query (SQLAlchemy)

Archivo: `src/osiris/core/db.py`

- Se instrumenta el engine con eventos:
  - `before_cursor_execute`
  - `after_cursor_execute`
  - `handle_error`
- Cada query registra:
  - tipo de sentencia (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, etc.)
  - duración
  - clasificación de query lenta por umbral configurable

### 2) Agregación de DB por request

Archivos:

- `src/osiris/core/observability.py`
- `src/osiris/main.py`

Por cada request se mide:

- cantidad total de queries
- tiempo total de DB del request
- cantidad de slow queries del request

Y se exporta a métricas agregadas por endpoint (`method` + `path`).

### 3) Métricas Prometheus añadidas

Endpoint: `GET /metrics`

Métricas nuevas Sprint 2:

- `osiris_db_queries_total{statement_type}`
- `osiris_db_query_duration_seconds_sum{statement_type}`
- `osiris_db_query_duration_seconds_count{statement_type}`
- `osiris_db_slow_queries_total{statement_type}`
- `osiris_http_db_queries_per_request_sum{method,path}`
- `osiris_http_db_queries_per_request_count{method,path}`
- `osiris_http_db_time_seconds_per_request_sum{method,path}`
- `osiris_http_db_time_seconds_per_request_count{method,path}`
- `osiris_http_requests_with_slow_db_queries_total{method,path}`

### 4) Headers opcionales de performance para troubleshooting

Archivo: `src/osiris/main.py`

Cuando `PERFORMANCE_RESPONSE_HEADERS_ENABLED=true` se devuelven:

- `X-DB-Query-Count`
- `X-DB-Time-MS`
- `X-DB-Slow-Query-Count`

Esto está diseñado para QA y diagnóstico en entornos controlados.

### 5) Logging estructurado extendido

Archivo: `src/osiris/core/observability.py`

Se agregan campos al log JSON por request:

- `db_query_count`
- `db_query_time_ms`
- `db_slow_query_count`

## Variables de entorno nuevas

Archivo: `src/osiris/core/settings.py`

- `OBSERVABILITY_DB_METRICS_ENABLED` (default: `true`)
- `OBSERVABILITY_DB_SLOW_QUERY_THRESHOLD_MS` (default: `300`, mínimo `1`)
- `PERFORMANCE_RESPONSE_HEADERS_ENABLED` (default: `false`)

## Validación técnica implementada

Pruebas:

- `tests/test_observability.py`
- `tests/test_observability_db.py`
- `tests/test_settings.py`
- `tests/test_security_access_audit.py` (se mantiene hardening de Sprint 1)

Cobertura:

- métricas DB por query y por request
- propagación de headers de performance cuando se habilitan
- validación de configuración de umbral de slow query

## Guía QA (ejecución rápida)

1. Habilitar headers de performance en entorno QA:

```bash
PERFORMANCE_RESPONSE_HEADERS_ENABLED=true
```

2. Ejecutar request funcional (ej. listado con DB) y validar headers:

- `X-DB-Query-Count`
- `X-DB-Time-MS`
- `X-DB-Slow-Query-Count`

3. Consultar `/metrics` y validar presencia de métricas Sprint 2:

- `osiris_db_queries_total`
- `osiris_db_slow_queries_total`
- `osiris_http_db_queries_per_request_*`
- `osiris_http_db_time_seconds_per_request_*`

4. Cambiar umbral de slow query para prueba controlada:

```bash
OBSERVABILITY_DB_SLOW_QUERY_THRESHOLD_MS=1
```

y validar incremento de `osiris_db_slow_queries_total`.

5. Ejecutar smoke de performance local:

```bash
make perf-smoke
```

Script utilizado: `scripts/perf_smoke.py` (latencia promedio/p50/p95/p99 y validación de errores).
