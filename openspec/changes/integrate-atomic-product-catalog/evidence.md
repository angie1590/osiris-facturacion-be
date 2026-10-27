# Evidencia Gate 7.2.1 — Preflight Producto

Fecha: 2026-10-27. Entorno: PostgreSQL local de desarrollo en `127.0.0.1:5435`. No se ejecutó migración, backfill, seed ni escritura; no se modificaron filas.

## Implementación

- `scripts/audit_catalog_integrity.py --product-cutover` reutiliza el auditor global en transacción PostgreSQL `REPEATABLE READ` y `READ ONLY`.
- El reporte compara `tbl_producto.categoria_principal_id` con el bridge si la columna existe; si todavía no existe, reporta candidatos legacy unívocos y válidos. No persiste candidatos.
- Se añadieron diagnósticos de EAV activo no aplicable, valor inválido, valores duplicados y remapeo pendiente; el modo cutover bloquea productos activos que siguen en un bucket B3 válido. Los buckets B3 continúan aceptados por el preflight general.
- El auditor de perfil fiscal existente se mantiene complementario: ejecutado contra la DB local informó 24 relaciones, todas `INACTIVE_ASSIGNMENT`; no reportó asignaciones fiscales activas.

## Resultado local

- Schema aún legacy: `tbl_producto` no tiene `categoria_principal_id`.
- Conteos: 39 categorías, 21 atributos, 19 mappings, 19 productos (todos inactivos), 19 relaciones bridge, 106 valores EAV, 0 remapeos y 22 unidades.
- `--product-cutover --summary`: 19 conflictos `PRODUCT_CATEGORY_INVALID`, 0 candidatos seguros de backfill y `apto_para_migrar=false`.
- Verificación agregada READ ONLY: las 19 relaciones de esos productos apuntan a categorías inactivas; 0 apuntan a categorías activas, inexistentes o buckets `is_default`.
- Interpretación: no se escoge ni reactiva categoría automáticamente. El preflight de cutover permanece bloqueado hasta reconciliación administrativa explícita, aunque la primera migración aditiva nullable no se descarta por este resultado.

## Checks

- `tests/test_catalog_preflight.py` y `tests/test_product_tax_company_audit.py`: 23 passed.
- Ruff en los archivos Python del preflight: limpio.
- `openspec validate integrate-atomic-product-catalog --strict --no-interactive`: válido en backend y frontend.
