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
- Interpretación de ese preflight inicial: no se escogió ni reactivó categoría automáticamente; 2.3 quedó pendiente hasta una decisión administrativa. La resolución autorizada documentada abajo retiró explícitamente esos productos y sus dependencias, sin backfill inferido.

## Checks

- `tests/test_catalog_preflight.py` y `tests/test_product_tax_company_audit.py`: 23 passed.
- `tests/test_catalog_integrity_migrations.py`: 99 passed, 13 skipped, incluyendo pruebas upgrade/downgrade/upgrade y conflicto FK/bridge sin mutación en SQLite y PostgreSQL aislados.
- Suite BE completa después del cambio: 1289 passed, 80 skipped, 0 failed.
- Ruff en los archivos Python del preflight: limpio.
- Mypy focal del preflight y entidad Producto: limpio.
- `openspec validate integrate-atomic-product-catalog --strict --no-interactive`: válido en backend y frontend.

## Gate 7.2.2 — Migración aditiva

- Baseline antes de migrar: Alembic `f04b7c2a9e61`; se creó la etiqueta local `pre-entrega-7-producto-integral` en backend y frontend.
- Respaldo custom PostgreSQL validado con `pg_restore --list`: `/tmp/osiris_facturacion_pre_entrega7_20261027.dump`; SHA-256 `a8945089bdfa519d55aafd580f99fb0653a22b30c3c2a530c7e5d4522d076b12`.
- Revisión aplicada en desarrollo: `f51c8a2d7e90`; añade `categoria_principal_id UUID NULL`, FK a `tbl_categoria` e índice `ix_tbl_producto_categoria_principal_id`. No agrega `NOT NULL`, `CHECK`, backfill ni elimina el bridge.
- Postflight: 19 productos, 19 `categoria_principal_id IS NULL`, 0 valores poblados y 19 relaciones bridge intactas; FK e índice presentes; Alembic `current` coincide con `head`.
- El preflight sigue bloqueando el cutover con 19 `PRODUCT_CATEGORY_INVALID` y 0 candidatos seguros porque las 19 categorías legacy están inactivas. No se escogió ni reactivó ninguna categoría; Gate 7.2.3 queda pendiente de reconciliación administrativa.

## Gate 7.2.3 — Resolución autorizada del legacy local

- El mantenedor autorizó explícitamente eliminar los 19 productos inactivos y sus dependencias, incluyendo 51 relaciones de bodega con 400 unidades, 106 valores EAV, 19 relaciones de categoría, 24 impuestos y 21 relaciones de proveedores. La autorización se confirmó después de mostrar los conteos; se preservaron 38 filas de `audit_log`.
- Antes del DELETE se creó y verificó `/tmp/osiris_facturacion_pre_delete_products_20261027.dump` con `pg_restore --list`; SHA-256 `231370204544c4da163a81d3a257f4095b4604f1edec3e5f8598abe51ae67a0e`.
- El borrado se ejecutó en una transacción con aserciones exactas para los 19 productos, cada relación dependiente y las 400 unidades; cualquier variación habría abortado el commit. No había filas de stock materializado, detalles de movimientos, compras ni ventas asociadas y la cantidad agregada en `tbl_producto` era cero.
- Postflight: 0 productos y 0 relaciones bridge/EAV/bodega/impuestos/proveedores del conjunto; 39 categorías, 21 atributos y 19 mappings sin cambios. `audit_catalog_integrity.py --product-cutover --summary` informa `apto_para_migrar=true`, 0 conflictos y 0 candidatos backfill. La columna nueva se conserva nullable; no se activó CHECK/NOT NULL.
- Resultado de suites posterior a la corrección del preflight: backend 1289 passed, 80 skipped; migraciones PostgreSQL/SQLite 99 passed, 13 skipped; Ruff, mypy y OpenSpec estricto limpios.

## Gate 7.3.1 — DTO integral

- Se añadieron `ProductoIntegralCreate`, `ProductoIntegralUpdate` y `ProductoAtributoIntegralInput` con `categoria_principal_id`, perfil tributario, atributos por UUID y valor escalar tipado.
- Los DTOs nuevos prohíben campos extras: `categoria_ids` y `usuario_auditoria` no entran en el contrato canónico. Los DTOs legacy existentes no cambiaron y las rutas todavía no usan los nuevos modelos.
- Alta exige perfil tributario no vacío y categoría; update conserva `atributos` omitido como `None` y acepta `precondicion_preview`; ambas rechazan atributos duplicados y normalizan PVP a dos decimales.
- `tests/test_producto_integral_models.py`: 5 passed. Ruff, mypy focal y OpenSpec strict: limpios.
- La validación de pertenencia al resolver efectivo, obligatoriedad y perfil tributario real permanece en el servicio transaccional 3.2; estos DTOs solo validan estructura/tipos.

## Gate 7.3.2 — Alta integral transaccional

- `ProductoService.create_integral` usa el DTO canónico y persiste Producto con FK principal, una proyección bridge, perfil fiscal, EAV y eventos de auditoría en la sesión existente; hace un solo `commit` al final y revierte toda la sesión ante error.
- Valida categoría activa/hoja/no temporal, aplicabilidad por resolver efectivo, obligatorios con default explícito o valor enviado, impuesto vigente/configurado/compatible y UUID de atributos; el actor se deriva de `get_current_usuario` y se establece en contexto de auditoría.
- `POST /api/v1/productos` despacha al DTO integral nuevo o al DTO legacy para compatibilidad. La autorización del endpoint sigue temporalmente por rol y se sustituirá por permisos efectivos en 3.4; no se marca esa parte como completada.
- `tests/test_producto_integral_service.py`: alta guarda FK/bridge/IVA/default EAV/auditoría; faltante obligatorio, atributo no aplicable e impuesto inválido responden errores canónicos y revierten todas las filas del producto.
- Suite BE completa: 1298 passed, 80 skipped; tests legacy/DTOs/servicio y Ruff/mypy focales limpios; OpenSpec estricto válido.
- La DB local conserva 0 productos tras la limpieza autorizada de 7.2.3; estas pruebas usan SQLite aislado y no sembraron datos compartidos.

## Gate 7.3.3 — Edición integral

- `ProductoService.update_integral` bloquea la fila Producto, verifica consistencia FK/bridge y solo permite mantener la categoría actual hasta implementar preview 7.4. General fields, taxes, EAV y auditoría comparten una sesión/commit.
- Colección de atributos omitida conserva valores existentes; `null` desactiva lógicamente solo atributos opcionales y retiene la fila/valor histórico. Un obligatorio `null`, un atributo no aplicable o un valor inválido abortan la transacción.
- Cambio de categoría sin preview devuelve `409 PRODUCT_CATEGORY_CHANGE_REQUIRES_PREVIEW` sin mutar el producto.
- `tests/test_producto_integral_service.py`: 8 passed, incluyendo rollback completo de update cuando un EAV falla después de modificar un dato general. Suite BE completa: 1302 passed, 80 skipped; Ruff/mypy focales limpios.

## Gate 7.3.4 — Permisos efectivos de Producto

- `PRODUCTOS.leer/crear/actualizar/eliminar` se verifica mediante `product_permission`; CRUD, opciones fiscales, EAV, impuestos y proveedores ya no dependen de nombres de rol.
- La migración `c8d7e9f1a204` crea `PRODUCTOS` y copia grants activos faltantes de `INVENTARIO` sin sobrescribir los existentes. Se aplicó en PostgreSQL local; matriz postflight: Administrador y Jefe de Almacén full, Vendedor lectura solamente.
- `scripts/seed_data_structure.yaml` incluye la misma matriz para instalaciones nuevas. `RolModuloPermisoService` entrega también PRODUCTOS al administrador.
- `tests/test_product_permissions_migration.py` e `tests/test_catalog_permissions.py`: 112 passed; suite BE completa tras actualizar fixtures de auth: 1308 passed, 80 skipped. Ruff/mypy limpios.
- Las rutas de `producto_bodega` quedan como subflujo separado de inventario; no se modificaron reglas ni datos de stock en esta entrega.

## Gate 7.3.5 — Rollback integral

- `tests/test_producto_integral_service.py` fuerza error en bridge, taxes, EAV y auditoría dentro del alta; en los cuatro casos se verifica rollback de Producto, FK/bridge, impuestos, EAV y eventos generados por el alta.
- La edición same-category también prueba rollback de campos generales, EAV y audit ante valor inválido.
- Suite BE final: 1312 passed, 80 skipped, 0 failed. Ruff y mypy focales limpios.
