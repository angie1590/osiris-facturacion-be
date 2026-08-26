---
sidebar_position: 3
---

# Resiliencia Operativa Sprint 3

## Objetivo

Agregar controles operativos de resiliencia para producción bajo carga, sin alterar reglas de negocio:

- backpressure por límite de requests concurrentes
- health checks live/ready
- métricas operativas de saturación y readiness

## Alcance técnico implementado

### 1) Guard de saturación por requests en vuelo

Archivo: `src/osiris/main.py`

- Se evalúa `SCALABILITY_MAX_IN_FLIGHT_REQUESTS`.
- Si el límite se alcanza:
  - responde `503 Service Unavailable`
  - conserva `X-Request-ID`
  - registra métrica de rechazo por saturación
  - no ejecuta lógica de negocio

### 2) Endpoints operativos de salud

Archivo: `src/osiris/main.py`

- `GET /health/live`
  - estado de vida del proceso API (`200`).
- `GET /health/ready`
  - valida disponibilidad de DB con `SELECT 1`.
  - retorna:
    - `200` -> `{ "status": "ok", "database": "up" }`
    - `503` -> `{ "status": "degraded", "database": "down" }`

### 3) Métricas nuevas Sprint 3

Endpoint: `GET /metrics`

- `osiris_http_overload_rejections_total{method,path}`
- `osiris_health_readiness_checks_total{status}`

Estas métricas permiten:

- detectar saturación real de capa API
- monitorear estabilidad de readiness/DB para autoscaling o alertas

## Variables de entorno nuevas

Archivo: `src/osiris/core/settings.py`

- `SCALABILITY_MAX_IN_FLIGHT_REQUESTS` (default: `0`)
  - `0` = desactivado
  - `> 0` = límite de requests concurrentes

## Recomendación operativa inicial

- staging:
  - `SCALABILITY_MAX_IN_FLIGHT_REQUESTS=64`
- producción:
  - ajustar según CPU, workers y latencia objetivo

## Validación técnica

Pruebas:

- `tests/test_scalability_health.py`
- `tests/test_settings.py`
- `tests/test_observability.py`

Cobertura:

- rechazo `503` por saturación
- funcionamiento de `/health/live` y `/health/ready`
- validación de configuración de límite de in-flight requests

## Guía QA (resumen)

1. Setear `SCALABILITY_MAX_IN_FLIGHT_REQUESTS=1`.
2. Forzar condición de saturación y validar `503`.
3. Consultar `/health/live` y validar `200`.
4. Consultar `/health/ready` con DB up/down y validar `200/503`.
5. Revisar en `/metrics` incremento de:
   - `osiris_http_overload_rejections_total`
   - `osiris_health_readiness_checks_total`
