---
sidebar_position: 7
---

# DR y Continuidad Enterprise

## Objetivo

Formalizar continuidad operativa con evidencia de backup/restore verificable.

## Controles implementados

1. Backup operativo:
   - target: `make dr-backup`
   - genera SQL dump en `backups/`.

2. Verificación de restauración:
   - target: `make dr-verify`
   - crea dump temporal, restaura en DB de verificación y valida tablas restauradas.
   - elimina DB temporal al finalizar.

## Criterio de aceptación DR

Para estado enterprise:

1. `make dr-verify` en PASS de forma periódica.
2. Evidencia de última verificación DR archivada por entorno.
3. Política de retención de backups definida por operación.

## Objetivos operativos recomendados

1. RPO objetivo: `<= 15` minutos.
2. RTO objetivo: `<= 60` minutos.
3. Prueba DR completa: al menos 1 vez por mes en ambiente no productivo.

## Comandos

```bash
make dr-backup
make dr-verify
```
