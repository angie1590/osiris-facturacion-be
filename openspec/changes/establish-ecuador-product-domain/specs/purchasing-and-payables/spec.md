## ADDED Requirements

### Requirement: Compra integrada
El sistema SHALL registrar una compra con proveedor, comprobante, impuestos, productos y bodega y SHALL crear su ingreso de inventario en la misma unidad transaccional.

#### Scenario: Compra válida
- **WHEN** se registra una compra desde productos configurados
- **THEN** se crean compra, detalles, ingreso confirmado y obligación por pagar aplicable

### Requirement: Reverso de compra
El sistema SHALL anular una compra elegible mediante movimientos inversos y trazabilidad, sin borrar el documento original.

#### Scenario: Anulación con stock disponible
- **WHEN** se anula una compra y el stock permite el reverso
- **THEN** se revierte el ingreso y se conserva el historial de estado