## Why

Las tarifas tributarias excepcionales emitidas por decreto tienen alcance y vigencia limitados; aplicar manualmente cambios al catálogo permanente puede afectar ventas fuera del periodo o productos no elegibles. El sistema necesita administrar esas reglas explícitamente y calcularlas de forma reproducible por venta, conservando lo aplicado para auditoría.

## What Changes

- Añadir medidas tributarias temporales configurables con impuesto, periodo inclusivo, tarifa/código SRI confirmados, estado y alcance explícito por productos.
- Exigir habilitación administrativa deliberada; medidas en borrador o sin alcance/código validado nunca alteran cálculos.
- Evaluar la fecha de emisión y el producto al calcular IVA/ICE, aplicando una sola medida elegible por impuesto y producto.
- Guardar en cada línea de venta una instantánea de tarifa, código SRI y medida utilizada; los documentos históricos no cambiarán al editar o vencer una medida.
- Incorporar administración en el frontend con formulario/listado reutilizando componentes comunes; no inferir elegibilidad por la empresa, descripción libre o fechas del sistema.
- Soportar como datos configurables los ejemplos de reducción IVA turística y reducción ICE a productos cerveceros, sin precargar códigos/tarifas SRI no confirmados.

No incluye importación automática de decretos, asesoría legal, clasificación automática de turismo/cerveza, cambios a compras/retenciones ni reliquidación de ventas existentes.

## Capabilities

### New Capabilities
- `temporary-tax-measures`: Administración, vigencia, alcance, evaluación y trazabilidad de medidas tributarias temporales.

### Modified Capabilities

## Impact

- Backend: nuevo dominio/API y migración Alembic; cálculo/hidratación de ventas, snapshots, auditoría y mapeo FE-EC.
- Frontend: nueva sección administrativa para medidas temporales y selección explícita de productos elegibles.
- SRI: la tarifa y código de porcentaje aplicados deben estar confirmados para el ambiente/regla vigente; no se inventan códigos ni se modifica el catálogo base.
- Inventario: solo lectura de productos elegibles; no cambia stock, movimientos, costo ni valoración.
- Cartera: usa el total de venta ya calculado, sin lógica tributaria propia.
- Multiempresa: el acceso de gestión se limita a permisos administrativos existentes; no se habilita aplicación cruzada por selección del cliente.
