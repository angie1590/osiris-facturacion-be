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

## Gate 7.4.1/7.4.2 — Preview de cambio de categoría

- `POST /api/v1/productos/{id}/previsualizar-cambio-categoria` usa `PRODUCTOS.actualizar`, signer `CatalogPreviewSigner` y liga operación, target, actor, payload, FK/bridge, cadenas jerárquicas (incluida hoja/B3), mappings efectivos, EAV activo e impuestos/configuración empresarial.
- El preview es read-only y expone IDs/nombres/rutas de categorías, conservados, desactivados, defaults explícitos, faltantes, incompatibles y conteos de nuevos obligatorios. Atributos compartidos se relacionan por `atributo_id`; un valor de categoría origen se reporta como desactivado, no como desconocido.
- `tests/test_producto_integral_service.py` comprueba impacto con shared/removed/default/required, propuesta inválida, `null` obligatorio, token rechazado al cambiar actor o mapping y snapshots sin cambios.
- En el checkpoint previo a 4.3: suite focal servicio/RBAC 123 passed; suite BE completa tras el preview 1313 passed, 80 skipped. Ruff, mypy y strict OpenSpec limpios.

## Gate 7.4.3 — Confirmación de cambio de categoría

- `update_integral` adquiere lock de jerarquía y `FOR UPDATE` de Producto, valida FK/bridge, canonicaliza payload, verifica token contra actor/target/estado actual y vuelve a calcular faltantes/incompatibles antes de escribir.
- La confirmación sincroniza FK y una sola fila bridge, aplica valores compartidos/proporcionados/defaults explícitos y desactiva lógicamente EAV no aplicable conservando su valor histórico; todo se confirma con un único commit.
- Sin token o con actor/payload/mapping cambiado, la operación se rechaza sin modificar el producto. Test de confirmación válida verifica FK/bridge destino, valor EAV compartido y valor antiguo desactivado; test stale verifica `409 CATALOG_PREVIEW_STALE`.
- Test PostgreSQL real `test_postgresql_concurrent_category_mapping_change_rejects_confirmation_atomically`: en un schema UUID temporal, sesión A mantiene el advisory lock y cambia un default; sesión B intenta confirmar con el token anterior y se observa esperando en `pg_locks`. Tras el commit de A, B recibe `409 CATALOG_PREVIEW_STALE`; el mapping nuevo queda persistido y el producto conserva FK, bridge y EAV anterior. El schema se elimina en `finally`.
- Ejecución opt-in contra PostgreSQL local publicado en `127.0.0.1:5435`: 1 passed. La suite general omite el test si `CATALOG_TEST_DATABASE_URL` no está configurado.
- También hay prueba SQLite de cambio entre sesiones secuenciales, preview HTTP 200 serializado/read-only, preview faltante y rollbacks totales.
- Suite focal contracts/service/RBAC/preflight/fiscal: 156 passed. Verificación final tras la auditoría con PostgreSQL opt-in: 1406 passed, 14 skipped, 0 failed. Ruff limpio, mypy en 350 archivos sin errores, snapshot de contrato y OpenSpec strict válidos.
- `get_producto_completo` y listado ahora usan `categoria_principal_id` cuando está definido; exponen `categoria_principal`/`categoria_ruta`, y atributos efectivos incluyen UUID, unidad, origen y herencia. `categorias[]` se mantiene como proyección legacy.
- Prueba HTTP hace divergir FK y bridge y verifica que detalle/listado y origen de atributos siguen FK. Los fallos inesperados de atributos/bodegas producen códigos estables en vez de listas vacías. OpenAPI documenta datos generales, categoría/ruta, atributos/metadatos y bodegas con cantidad/IDs.
- `tests/test_producto_completo_atributos_e2e.py`: 7 passed; test OpenAPI aislado: 1 passed. Cliente FE prueba rutas/payloads integrales; suite FE y build pasan.
- Los smoke BE crean la tabla EAV en SQLite de prueba; se conserva `PRODUCT_ATTRIBUTE_RESOLUTION_FAILED` para fallos reales de resolución y se registra el traceback solo en log interno.
- La confirmación de cambio de categoría persiste también defaults explícitos calculados por backend, junto a valores enviados, bajo el token vigente; el test confirma el valor EAV persistido.
- E2E browser autenticado: alta integral, edición con un PUT, preview y cambio Teclado→Mouse confirmados con token; IVA 0% y default explícito Núm. Botones=3.
- UUID temporal `622a198f-c7b4-4488-a515-2bcec7fadc43` limpiado por UUID en una transacción. El postflight confirmó conteo cero en Producto, bridge, EAV, impuestos, bodegas, inventario/stock, movimientos, compras y ventas. Se limpiaron exclusivamente sus 11 filas de auditoría.
- El E2E no modificó la empresa ni el catálogo SRI. El 409 restante corresponde a `GET /categorias/sin-clasificar/conteo`, que requiere un scope explícito y no bloquea Producto.
- El 409 fiscal se debía a ausencia de `X-Empresa-Id`, no a falta de IVA: el cliente no tiene selector global y el JWT no lleva empresa. `resolve_product_tax_company` ahora infiere scope solo si existe exactamente una empresa activa; cero/múltiples empresas siguen rechazándose con 409. Pruebas unitarias cubren ambos casos.
- Verificación live después de reiniciar el backend: `GET /api/v1/productos/impuestos-disponibles?tipo_producto=BIEN` devuelve 200 con IVA 0%; el formulario live lo muestra seleccionado. La empresa no se modificó.
- Configuración fiscal corregida según regla de negocio: `Empresa.impuesto_catalogo_ids` admite múltiples tarifas activas (IVA 0%, 15%, exento y/o ICE); guardar la empresa con lista vacía devuelve 400 y ya no inserta IVA 0% automáticamente. Cada producto elige su tarifa IVA y puede añadir ICE. Test BE cubre varias tarifas empresariales y productos con tarifas distintas.
- `EmpresaService._validate_company_taxes` conserva todos los IDs seleccionados válidos (deduplicados) y el helper smoke envía IVA 0% explícitamente.
- `tests/test_empresa_configuration.py` cubre rechazo de lista vacía, varias tarifas activas, conservación de IVA 15% elegido y ausencia de IVA 0% implícito; `tests/test_empresa.py` conserva las pruebas de reglas tributarias no fiscales.
- Gate 7.7.1/7.7.2: preflight PostgreSQL READ ONLY post-E2E `apto_para_migrar=true`, 0 conflictos y 0 productos/bridge/EAV; auditoría fiscal 0 relaciones. Preflight aplicado contra `127.0.0.1:5435`.
- Backup previo al CHECK: `/tmp/osiris_facturacion_pre_cutover_20261028.dump`, SHA-256 `871aa7875d1b6561a2f82dd9e717f4879c8e2c0261c72c7f23346eb4b4194ae8`, `pg_restore --list` con 612 entradas.
- Gate 7.7.3: migración `d3b9e8a1c6f4` aplicada; `alembic current=head`; CHECK `ck_tbl_producto_active_requires_category` presente. Prueba PostgreSQL directa confirmó que `activo=true` + FK nula falla y no persiste fila. Writes legacy de una categoría sincronizan FK/bridge; cero/múltiples categorías se rechazan. La lectura canónica no deriva la FK desde el bridge.
- Postflight Gate 7.7.1/7.7.2/7.7.3 en PostgreSQL local: Alembic `d3b9e8a1c6f4`, `categoria_principal_id` presente, 0 productos, `audit_catalog_integrity.py --product-cutover --summary` apto con 0 conflictos/candidatos y auditoría fiscal con 0 relaciones.
- El bridge y `categorias[]` se conservan como proyección/compatibilidad hasta el inventario final de consumidores y postflight 7.7.4.
- Preparación 7.7.4: detalle/listado, EAV, preview B3, backfill/impacto de mappings, recategorización B3, limpieza de defaults y bajas consultan `categoria_principal_id`; las mutaciones B3 actualizan FK y bridge en la misma transacción. `tbl_producto_categoria` permanece solo para sincronizar compatibilidad y para guardas explícitas de divergencia en preview/update integral.
- Correcciones auditoría P0: preview acepta un obligatorio nuevo proporcionado manualmente con/sin EAV previo; confirmación stale concurrente PostgreSQL conserva `409 CATALOG_PREVIEW_STALE`; auditor fiscal prioriza `INACTIVE_TAX`/`EXPIRED_TAX` frente a asignación inactiva. Pruebas focales BE pasan.
- Correcciones P1: categoría B3 actual permite editar datos generales y cambiar a hoja normal mediante preview; update integral requiere `expected_updated_at` y rechaza versión vieja con `409 PRODUCT_STATE_CHANGED`, probado en SQLite y PostgreSQL. `POST/PUT /productos` solo aceptan DTO integrales; `PUT /productos/{id}/atributos` devuelve 410 `LEGACY_PRODUCT_WRITE_DISABLED`. FE eliminó formularios, rutas y hooks de escritura sin callers.
- Gate 6.4 completado localmente: `f6a2c9d1e740` retiró `tbl_producto_categoria` después de backup, preflight READ ONLY `apto_para_migrar=true`/0 conflictos/0 duplicados, e índice unique previo `e1f4a8d63c20`. Postflight: Alembic `f6a2c9d1e740`, tabla bridge ausente, 0 productos, auditor de catálogo apto usando solo FK. Downgrade recrea el bridge desde FK. GET legacy categoría-atributo responde 410 y el inventario FE no tiene callers.
- Correcciones P2: detalle distingue ID `ProductoBodega` y `bodega_id`; listado global muestra productos sin bodega; selector devuelve `ruta`/`ruta_texto`; formulario oculta acciones si faltan permisos efectivos de categorías/atributos; detalle incluye `activo`/`actualizado_en`; edición registra evento resumen `UPDATE_PRODUCT_INTEGRAL`. Preview valida atributos destino, unicidad y acciones confirmables.
- Instalación/CI: `scripts/bootstrap_fe_ec_wheel.sh` descarga URL privada y verifica SHA-256 antes de Poetry; `.github/workflows/backend.yml` ejecuta Ruff, mypy, suite y PostgreSQL. El script se validó con el wheel local. El remoto backend es público; no se publicó el wheel. La ejecución CI queda bloqueada hasta disponer de almacenamiento privado y configurar `FE_EC_WHEEL_URL`, `FE_EC_WHEEL_SHA256` y opcionalmente `FE_EC_WHEEL_TOKEN` como secrets.
- Accesibilidad: los diálogos compartidos garantizan descripción accesible aunque no haya texto visible. Build docs pasa; audit docs mantiene 5 advisories bajos con fix sugerido que implica downgrade mayor, no aplicado. No se reprodujo una advertencia de HTML anidado en los diálogos modificados; requiere verificación browser adicional.
- Verificación final coordinada: BE con PostgreSQL opt-in 1406 passed, 14 skipped, 0 failed; Ruff, mypy en 350 archivos, OpenAPI snapshot, OpenSpec strict y YAML CI válidos. FE 349 passed, lint/build y OpenSpec strict válidos; `npm audit` reporta 0 vulnerabilidades frontend. Build Docusaurus exitoso; auditoría docs mantiene 5 vulnerabilidades bajas.
- Gate 7.1: tres pruebas PostgreSQL opt-in pasan para rollback integral ante fallo EAV, confirmación stale por mapping concurrente y edición optimista concurrente. La suite incluye permisos efectivos y eventos de auditoría transaccionales.
- Gate 7.4: runbook operativo `ops/product-catalog-cutover-runbook.md`; postflight read-only del 2026-11-04 reporta 0 productos, EAV/impuestos/bodegas, stock, kardex/movimientos, compras/CxP, ventas/CxC, retenciones, SRI/documentos; 252 filas de auditoría existentes preservadas. Migración DDL no escribe eventos de negocio.
- Respaldo usado antes del drop: `/tmp/osiris_facturacion_pre_bridge_drop_20261104.dump`, 314.815 bytes, 613 entradas en `pg_restore --list`, SHA-256 `454f930b60bca6eb9e87da93e3dd4a7f3acfd79439e09582167317a107440050`.
- Revalidación final 2026-11-04 después de retirar el bridge: BE 1.408 passed/14 skipped; Ruff, mypy (351 archivos), snapshot OpenAPI, OpenSpec estricto y build Docusaurus pasan. FE 349 passed, lint y build pasan. `npm audit` reporta 10 moderadas y 0 altas/críticas; no se aplicó una actualización de dependencias fuera del alcance.
- El cutover verificado corresponde al PostgreSQL local de desarrollo. Para producción, ejecutar el mismo backup/preflight/upgrade/postflight; los consumidores externos y CI privado `fe_ec` requieren coordinación del mantenedor.
