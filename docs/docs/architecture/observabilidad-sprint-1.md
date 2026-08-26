---
sidebar_position: 1
---

# Observabilidad Sprint 1

## Objetivo

Agregar observabilidad transversal del backend sin alterar reglas de negocio:

- Trazabilidad por request (`X-Request-ID`).
- Logging estructurado JSON.
- Métricas Prometheus para HTTP, seguridad y worker FE.

## Componentes implementados

### 1) Middleware de observabilidad HTTP

Archivo: `src/osiris/main.py`

- Genera `X-Request-ID` si no viene en el request.
- Propaga `X-Request-ID` en la respuesta.
- Registra latencia por request.
- Incrementa contadores HTTP y gauge de requests en vuelo.

### 2) Logging estructurado JSON

Archivo: `src/osiris/core/observability.py`

- Formato JSON con:
  - `timestamp`, `level`, `logger`, `message`
  - `request_id`, `user_id`, `company_id`
  - `method`, `path`, `status_code`, `latency_ms`, `client_ip`

### 3) Métricas Prometheus

Endpoint: `GET /metrics` (fuera de Swagger)

Métricas:

- `osiris_http_requests_total{method,path,status_code}`
- `osiris_http_request_duration_seconds_sum{method,path}`
- `osiris_http_request_duration_seconds_count{method,path}`
- `osiris_http_in_flight_requests`
- `osiris_security_unauthorized_access_total{reason}`
- `osiris_fe_worker_runs_total`
- `osiris_fe_worker_processed_documents_total`
- `osiris_fe_worker_errors_total`

### 4) Instrumentación de seguridad sensible

Archivo: `src/osiris/main.py`

Cuando ocurre acceso no autorizado en endpoints sensibles se incrementa:

- `osiris_security_unauthorized_access_total{reason="missing_user"}`
- `osiris_security_unauthorized_access_total{reason="insufficient_permissions"}`
- `osiris_security_unauthorized_access_total{reason="endpoint_returned_403"}`

### 5) Instrumentación del worker FE

Archivo: `src/osiris/main.py`

En cada ciclo del worker FE:

- Se registra ejecución: `osiris_fe_worker_runs_total`.
- Se registra volumen procesado: `osiris_fe_worker_processed_documents_total`.
- En excepción: `osiris_fe_worker_errors_total`.

## Variables de entorno

Archivo: `src/osiris/core/settings.py`

- `OBSERVABILITY_JSON_LOGS_ENABLED` (default: `true`)
- `OBSERVABILITY_METRICS_ENABLED` (default: `true`)
- `LOG_LEVEL` (`CRITICAL|ERROR|WARNING|INFO|DEBUG`, default: `INFO`)

## Ejemplos operativos

### Consultar métricas

```bash
curl -s http://localhost:8000/metrics
```

### Enviar request con trazabilidad explícita

```bash
curl -H "X-Request-ID: req-frontend-123" http://localhost:8000/openapi.json
```

## Validación técnica

Pruebas agregadas:

- `tests/test_observability.py`

Cobertura:

- Header `X-Request-ID` (propagado y autogenerado).
- Endpoint `/metrics`.
- Incremento de contador HTTP después de requests reales.
