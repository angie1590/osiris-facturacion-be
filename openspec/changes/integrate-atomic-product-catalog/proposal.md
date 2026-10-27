## Why

El producto todavía se clasifica mediante una colección `ProductoCategoria`, y el alta del frontend guarda sus valores EAV después de crear el producto. Sin una categoría principal autoritativa ni una escritura integral, un error puede dejar un producto incompleto; además, los consumidores de atributos y permisos siguen acoplados a contratos legacy.

La entrega 7 establece primero el contrato coordinado y después habilita un cutover aditivo: categoría principal, atributos efectivos, impuestos y auditoría se validarán y confirmarán como una sola operación, sin inferir clasificación ambigua ni tocar movimientos de inventario.

## What Changes

- Definir `Producto.categoria_principal_id` como autoridad futura de clasificación y `tbl_producto_categoria` únicamente como proyección temporal sincronizada por el servicio integral.
- Incorporar contratos integrales de alta, edición, detalle y previsualización/confirmación de cambio de categoría, incluidos los errores canónicos y semántica omitido/null/default.
- Exigir una categoría activa seleccionable, atributos efectivos válidos, perfil tributario permitido y actor autenticado para productos activos.
- Incorporar preflight de solo lectura y migración aditiva; solo backfillear una relación legacy inequívoca y bloquear conflictos para resolución explícita.
- Migrar permisos de las operaciones canónicas de Producto a permisos efectivos y mantener una transacción exterior que incluya Producto, categoría, impuestos, EAV y auditoría.
- **BREAKING, en el gate de cutover:** deprecar y finalmente rechazar `categoria_ids` múltiples y retirar fallback/bridge y GET legacy solo después de comprobar todos sus consumidores.
- No ejecutar migraciones ni cambiar formularios durante el Gate 7.1; no alterar stock, kardex, compras, ventas, cartera, SRI ni documentos.

## Capabilities

### New Capabilities
- `product-integral`: contratos backend para clasificación principal, persistencia integral, preview de cambio, lectura canónica, autorización, migración gradual e invariantes transaccionales.

### Modified Capabilities
- Ninguna. `openspec/specs/` no contiene capacidades vigentes; las decisiones previas de otros cambios se usarán como contexto, no como requisitos sincronizados implícitamente.

## Impact

- API y dominio: `src/osiris/modules/inventario/producto/`, entidades de categoría, atributos EAV e impuestos; nuevos permisos efectivos `PRODUCTOS`; OpenAPI y auditoría.
- Datos: migración Alembic nullable/aditiva, preflight y postflight sobre `tbl_producto` y `tbl_producto_categoria`; no hay cambio de datos en Gate 7.1.
- Calidad/documentación: pruebas de contrato, rollback, PostgreSQL, concurrencia y E2E; runbook y evidencia por gate.
- Límites: el catálogo de categorías/atributos permanece global. No se rediseñan reglas fiscales ni perfiles de empresa, y los proveedores/bodegas continúan fuera de la transacción del formulario mientras sean subflujos separados.
