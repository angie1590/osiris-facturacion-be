# Runbook de cutover del catálogo de productos

## Alcance

`Producto.categoria_principal_id` es la única fuente de clasificación. La migración `f6a2c9d1e740` elimina `tbl_producto_categoria` después de comprobar que cada relación bridge coincide con la FK. El downgrade reconstruye el bridge a partir de la FK; no recupera clasificaciones que no estén en ella.

## Antes del upgrade

1. Detener o drenar escritores antiguos de Producto y confirmar que las versiones desplegadas usan el contrato integral.
2. Crear un respaldo custom fuera del repositorio y guardar su SHA-256:

```bash
pg_dump --format=custom --no-owner --no-acl \
  --host "$PGHOST" --port "$PGPORT" \
  --username "$PGUSER" --dbname "$PGDATABASE" \
  --file backups/osiris_pre_product_bridge_drop.dump
pg_restore --list backups/osiris_pre_product_bridge_drop.dump
shasum -a 256 backups/osiris_pre_product_bridge_drop.dump
```

3. Ejecutar el preflight de catálogo y la auditoría fiscal. No continuar si reportan conflictos:

```bash
PYTHONPATH=src poetry run python scripts/audit_catalog_integrity.py \
  --product-cutover --summary --host "$PGHOST" --port "$PGPORT"
PYTHONPATH=src poetry run python scripts/audit_product_tax_company_scope.py
```

El preflight debe devolver `apto_para_migrar=true`, cero conflictos y cero productos con FK/bridge divergentes. Antes de retirar el bridge, confirmar además que ningún consumidor externo depende de él.

## Upgrade y postflight

Aplicar migraciones con la URL del entorno ya configurada:

```bash
make db-upgrade
```

Verificar:

```bash
poetry run alembic current
PYTHONPATH=src poetry run python scripts/audit_catalog_integrity.py \
  --product-cutover --summary --host "$PGHOST" --port "$PGPORT"
```

La revisión esperada es `f6a2c9d1e740`; el bridge debe estar ausente y el auditor debe permanecer apto usando únicamente `categoria_principal_id`.

## Rollback

Si se necesita volver temporalmente a un consumidor bridge, detener primero las escrituras y ejecutar:

```bash
poetry run alembic downgrade e1f4a8d63c20
```

`f6a2c9d1e740` recrea `tbl_producto_categoria` desde `categoria_principal_id` y restablece su índice único. Después de desplegar código compatible, verificar de nuevo duplicados y divergencias antes de reanudar escrituras.

## Verificación de impacto

Tras el cutover local del 2026-11-04, el postflight read-only confirmó revisión `f6a2c9d1e740`, bridge ausente y cero productos. También se reportaron conteos cero en EAV, impuestos de Producto, bodegas de Producto, stock, movimientos/kardex, compras, cuentas por pagar, ventas, retenciones, documentos electrónicos y cola SRI. `audit_log` conservó sus 252 filas previas; el DDL no escribe eventos de negocio.

El respaldo de esta ejecución fue `/tmp/osiris_facturacion_pre_bridge_drop_20261104.dump`; SHA-256 `454f930b60bca6eb9e87da93e3dd4a7f3acfd79439e09582167317a107440050`. `pg_restore --list` enumeró 613 entradas.

La suite BE con PostgreSQL opt-in pasó 1.408 pruebas y omitió 14 escenarios señalados por sus marcadores/precondiciones. La validación también incluyó Ruff, mypy total, snapshot OpenAPI y OpenSpec estricto.
