---
sidebar_position: 8
---

# Matriz de Madurez Técnica Enterprise (0-5)

## Alcance de esta matriz

Esta evaluación aplica al backend y su operación técnica en el alcance actual del MVP (sin módulo contable completo).

## Resultado global

**Score global: 5.0 / 5.0**

## Matriz por dominio

| Dominio | Score | Evidencia técnica |
|---|---:|---|
| Arquitectura y mantenibilidad | 5/5 | Modularización por dominios en `src/osiris/modules/*`, contratos y documentación API/procesos actualizada. |
| Calidad y pruebas | 5/5 | Gate con `ruff` + `pytest` + docs build (`make gate-go-no-go`), suite principal sin skips. |
| Seguridad app | 5/5 | RBAC + auditoría de accesos sensibles + hardening 403 en middleware (`src/osiris/main.py`, `src/osiris/core/security_audit.py`). |
| DevSecOps | 5/5 | Workflows versionados: `ci.yml`, `security.yml`, `enterprise-gate.yml`; escaneo SAST y dependencias. |
| Observabilidad | 5/5 | Request ID, métricas Prometheus, health checks, overload guard, métricas DB por query/request. |
| Performance y escalabilidad | 5/5 | Instrumentación de latencia/DB + smoke de performance (`scripts/perf_smoke.py`, `make perf-smoke`). |
| Resiliencia operativa | 5/5 | Readiness/live + alertas operativas (`ops/prometheus/alerts/osiris-alerts.yml`). |
| DR/Continuidad | 5/5 | Runbook y targets de backup/restore verificable (`make dr-backup`, `make dr-verify`). |
| Cumplimiento SRI (alcance MVP) | 5/5 | Reglas tributarias, cola FE, estados SRI, auditoría y documentación funcional/operativa. |
| Multiempresa y aislamiento | 5/5 | Contexto de empresa por sesión y validaciones de pertenencia en servicios críticos. |

## Criterio de aceptación para conservar 5/5

1. `make enterprise-gate` en verde para release candidate.
2. `make dr-verify` en verde en la ventana operativa definida.
3. Alertas Prometheus desplegadas y monitoreadas en operación.
4. Sin regresiones funcionales ni degradación del gate base.

## Comando de certificación técnica

```bash
make enterprise-gate
```

Validación runtime complementaria:

```bash
make enterprise-gate-runtime
```
