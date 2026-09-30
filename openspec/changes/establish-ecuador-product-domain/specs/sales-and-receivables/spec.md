## ADDED Requirements

### Requirement: Venta integrada
El sistema SHALL registrar una venta con comprador, productos, precios, impuestos, bodega y punto de emisión y SHALL crear su egreso de inventario al emitirla.

#### Scenario: Emisión con stock
- **WHEN** se emite una venta válida con stock suficiente
- **THEN** se asigna secuencial, se confirma el egreso y se crea la cuenta por cobrar aplicable

### Requirement: Totales inmutables
El sistema MUST conservar snapshots de descripción, precio e impuestos usados al emitir una venta.

#### Scenario: Cambio posterior del producto
- **WHEN** cambia el precio o impuesto del producto después de emitir
- **THEN** los valores históricos de la venta permanecen iguales