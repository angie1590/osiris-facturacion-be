## ADDED Requirements

### Requirement: Reportes derivados de fuentes canónicas
Los reportes SHALL calcular ventas, compras, cartera, tributación, inventario y rentabilidad desde documentos y movimientos canónicos, respetando empresa y período.

#### Scenario: Reporte de rentabilidad
- **WHEN** se consulta un período
- **THEN** ingresos y costos proceden de ventas no anuladas y egresos históricos vinculados

### Requirement: Auditoría de acciones sensibles
El sistema SHALL registrar actor, empresa, momento, entidad y transición para cambios sensibles.

#### Scenario: Anulación de venta
- **WHEN** un usuario autorizado anula una venta
- **THEN** la auditoría permite identificar quién, cuándo y por qué realizó la acción