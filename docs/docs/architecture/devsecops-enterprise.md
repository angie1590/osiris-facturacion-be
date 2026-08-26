---
sidebar_position: 5
---

# DevSecOps Enterprise

## Objetivo

Elevar el backend a un flujo enterprise verificable en CI/CD sin alterar la lógica de negocio.

## Controles implementados

1. CI de calidad y regresión:
   - workflow: `.github/workflows/ci.yml`
   - ejecuta `ruff`, `pytest` (suite principal) y build de documentación.
   - falla automáticamente si detecta `SKIPPED` en la suite principal.

2. Seguridad continua:
   - workflow: `.github/workflows/security.yml`
   - Bandit (SAST) sobre `src/`
   - pip-audit (dependencias Python vulnerables)
   - ejecución por PR, manual y semanal.

3. Gate enterprise versionado:
   - workflow: `.github/workflows/enterprise-gate.yml`
   - target: `make enterprise-gate`
   - incluye gate técnico base + escaneo de seguridad + auditoría de cobertura docs API.
   - política de ejecución estricta: ver [Política de Security Scan](./politica-security-scan).

## Comandos operativos locales

```bash
make gate-go-no-go
make security-scan
make enterprise-gate
```

Contingencia local (no válida para release):

```bash
make security-scan SECURITY_SCAN_STRICT=false
```

## Criterios de aceptación

Para considerar el control DevSecOps en verde:

1. `ci.yml` en PASS.
2. `security.yml` en PASS.
3. `enterprise-gate.yml` en PASS para release candidate.
4. Sin `SKIPPED` en suite principal.
