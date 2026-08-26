---
sidebar_position: 6
---

# Política de Security Scan (`pip-audit` / `bandit`)

## Objetivo

Definir una política operativa clara para ejecutar escaneo de seguridad de dependencias y SAST sin romper continuidad de desarrollo, manteniendo un estándar enterprise auditable.

## Comandos oficiales

```bash
# Escaneo de seguridad (modo estricto por defecto)
make security-scan

# Gate enterprise completo
make enterprise-gate
```

## Modo estricto y contingencia

`security-scan` usa la variable `SECURITY_SCAN_STRICT`:

- `SECURITY_SCAN_STRICT=true` (default):
  - `pip-audit` es bloqueante.
  - Cualquier hallazgo vulnerable o error de auditoría falla el gate.
- `SECURITY_SCAN_STRICT=false`:
  - Solo para contingencia local (por ejemplo, sin salida a internet).
  - El comando continúa con warning, pero **no certifica release**.

## Regla de uso por entorno

1. CI/CD de release candidate:
   - Obligatorio `SECURITY_SCAN_STRICT=true`.
   - Prohibido desactivar el modo estricto.
2. Entornos productivos/preproductivos:
   - Obligatorio `SECURITY_SCAN_STRICT=true`.
3. Desarrollo local:
   - Permitido `SECURITY_SCAN_STRICT=false` solo para desbloqueo temporal.
   - Debe regularizarse antes de abrir PR final.

## Dependencia local `fe-ec` (wheel)

El proyecto depende de un wheel local:

- `lib/fe_ec-0.1.0-py3-none-any-3.whl`

Durante `security-scan`, se ejecuta:

- `scripts/patch_feec_wheel_constraints.py`

Este script:
1. Normaliza en el `METADATA` del wheel la restricción de `cryptography`.
2. Recalcula `RECORD`.
3. Permite que `poetry lock --regenerate --no-cache` resuelva dependencias sin conflicto.

Alcance:
- No modifica la lógica funcional del backend.
- No modifica código Python de negocio de la librería.
- Ajusta metadatos de empaquetado para compatibilidad de seguridad.

## Criterios de aceptación (seguridad)

Para considerar seguridad en verde:

1. `make security-scan` en PASS con `SECURITY_SCAN_STRICT=true`.
2. `bandit` sin hallazgos bloqueantes.
3. `pip-audit` sin vulnerabilidades abiertas en dependencias productivas.
4. Evidencia de ejecución adjunta en PR o ticket de release.

## Manejo de excepciones

Si no se puede ejecutar en modo estricto (ejemplo: caída temporal de red):

1. Ejecutar localmente con `SECURITY_SCAN_STRICT=false` solo para continuar trabajo.
2. Registrar incidente técnico en ticket con:
   - fecha/hora,
   - motivo,
   - impacto,
   - responsable,
   - fecha compromiso de regularización.
3. Antes de merge/release: repetir escaneo estricto y adjuntar evidencia PASS.

## Ejemplos operativos

```bash
# Flujo normal (requerido para merge/release)
make security-scan

# Contingencia local temporal (no apto para release)
make security-scan SECURITY_SCAN_STRICT=false
```

## Relación con el Gate

- `make enterprise-gate` depende de `make security-scan`.
- Sin `security-scan` estricto en verde, el resultado final es **NO-GO** para release.
