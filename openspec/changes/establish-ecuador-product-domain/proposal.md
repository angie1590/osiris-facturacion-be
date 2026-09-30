## Why

El backend ya supera una base experimental y cuenta con 413 pruebas exitosas, pero sus capacidades no están formalizadas como contrato de producto. Documentarlas permitirá conservar el núcleo probado, cerrar brechas de producción SRI y evitar que la adaptación visual introduzca reglas incompatibles.

## What Changes

- Formalizar empresa, sucursales, puntos de emisión, usuarios, roles y alcance multiempresa como base operativa.
- Formalizar catálogo, impuestos por producto, bodegas, existencias, costo promedio, kárdex y movimientos directos.
- Definir compras como origen de ingreso de stock, cuentas por pagar y retenciones emitidas.
- Definir ventas como origen de egreso de stock, cuentas por cobrar y factura electrónica.
- Definir el ciclo de documentos SRI con cola, reintentos, XML autorizado, RIDE, impresión y auditoría.
- Prohibir autorizaciones simuladas en ambientes productivos cuando la integración FE-EC no esté disponible.
- Delimitar anulaciones del MVP como reversos trazables de documento e inventario, sin asientos de contabilidad general.

## Capabilities

### New Capabilities

- `organization-and-access`: empresa, establecimientos, puntos de emisión, usuarios, roles y aislamiento por empresa.
- `catalog-and-inventory`: productos, impuestos, bodegas, stock, costo promedio, kárdex y movimientos no comerciales.
- `purchasing-and-payables`: compras, ingreso de inventario, cuentas por pagar, pagos y retenciones emitidas.
- `sales-and-receivables`: ventas, egreso de inventario, cuentas por cobrar, cobros y retenciones recibidas.
- `ecuador-electronic-documents`: secuenciales, firma, envío SRI, cola, estados, XML, RIDE, impresión y anulación.
- `operational-reporting-and-audit`: reportes operativos/tributarios, historial y auditoría de acciones sensibles.

### Modified Capabilities

- Ninguna; este repositorio todavía no tenía especificaciones OpenSpec versionadas.

## Impact

- Código afectado: `src/osiris/modules/common`, `inventario`, `compras`, `ventas`, `sri`, `reportes` e `impresion`.
- API afectada: contratos bajo `/api/v1`, especialmente compras, ventas, movimientos y documentos electrónicos.
- Dependencias externas: PostgreSQL, FE-EC, certificados de firma, servicios de recepción/autorización del SRI y correo.
- Datos: se mantienen Alembic y los modelos actuales; cualquier consolidación requerirá migraciones compatibles y pruebas de reversión.