---
sidebar_position: 6
---

# SRE y Operación Enterprise

## Objetivo

Definir observabilidad y operación con umbrales accionables (SLO/alertas/runbook) para producción.

## Señales operativas

Endpoints:

- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`

Métricas críticas:

- `osiris_http_overload_rejections_total`
- `osiris_health_readiness_checks_total`
- `osiris_security_unauthorized_access_total`
- `osiris_fe_worker_errors_total`
- `osiris_db_slow_queries_total`

## Reglas de alerta

Archivo: `ops/prometheus/alerts/osiris-alerts.yml`

Alertas cubiertas:

1. `OsirisReadinessDown` (critical)
2. `OsirisOverloadRejectionsHigh` (warning)
3. `OsirisUnauthorizedAccessSpike` (warning)
4. `OsirisFEWorkerErrors` (critical)
5. `OsirisSlowQueriesDetected` (warning)

## SLO mínimo recomendado

1. Disponibilidad API (readiness up): 99.9% mensual.
2. Tasa de errores 5xx: < 0.5% por ventana de 5 min.
3. p95 de latencia endpoints críticos: < 700 ms.
4. Rechazos por sobrecarga: 0 en operación nominal.

## Runbook resumido

1. Readiness down:
   - validar DB connectivity.
   - revisar logs estructurados con `X-Request-ID`.
   - ejecutar rollback de despliegue si persiste > 10 min.

2. FE worker errors:
   - revisar cola SRI y mensajes.
   - diferenciar error de red vs rechazo lógico.
   - pausar emisión masiva y reprocesar controlado.

3. Slow queries:
   - identificar `statement_type` con mayor incidencia.
   - revisar índices y planes.
   - ajustar umbral `OBSERVABILITY_DB_SLOW_QUERY_THRESHOLD_MS` solo para diagnóstico.

