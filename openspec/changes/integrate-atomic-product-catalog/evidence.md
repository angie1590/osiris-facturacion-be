# Evidencia Gate 7.2.1 — Preflight Producto

Fecha: 2026-10-27. Entorno: PostgreSQL local de desarrollo en `127.0.0.1:5435`. Se aplicó únicamente la migración aditiva nullable descrita abajo; no se ejecutó backfill, seed ni modificación de filas de negocio.

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
- `tests/test_catalog_integrity_migrations.py`: 97 passed, 13 skipped, incluyendo pruebas upgrade/downgrade/upgrade en SQLite y PostgreSQL aislados.
- Ruff en los archivos Python del preflight: limpio.
- Mypy focal del preflight y entidad Producto: limpio.
- `openspec validate integrate-atomic-product-catalog --strict --no-interactive`: válido en backend y frontend.

## Gate 7.2.2 — Migración aditiva

- Baseline antes de migrar: Alembic `f04b7c2a9e61`; se creó la etiqueta local `pre-entrega-7-producto-integral` en backend y frontend.
- Respaldo custom PostgreSQL validado con `pg_restore --list`: `/tmp/osiris_facturacion_pre_entrega7_20261027.dump`; SHA-256 `a8945089bdfa519d55aafd580f99fb0653a22b30c3c2a530c7e5d4522d076b12`.
- Revisión aplicada en desarrollo: `f51c8a2d7e90`; añade `categoria_principal_id UUID NULL`, FK a `tbl_categoria` e índice `ix_tbl_producto_categoria_principal_id`. No agrega `NOT NULL`, `CHECK`, backfill ni elimina el bridge.
- Postflight: 19 productos, 19 `categoria_principal_id IS NULL`, 0 valores poblados y 19 relaciones bridge intactas; FK e índice presentes; Alembic `current` coincide con `head`.
- El preflight sigue bloqueando el cutover con 19 `PRODUCT_CATEGORY_INVALID` y 0 candidatos seguros porque las 19 categorías legacy están inactivas. No se escogió ni reactivó ninguna categoría; Gate 7.2.3 queda pendiente de reconciliación administrativa.
