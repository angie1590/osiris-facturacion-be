## ADDED Requirements

### Requirement: Stock por producto y bodega
El sistema SHALL mantener existencias y costo promedio por producto y bodega mediante movimientos confirmados e inmutables.

#### Scenario: Movimiento confirmado
- **WHEN** se confirma un movimiento válido
- **THEN** stock, costo y kárdex quedan sincronizados en una transacción

### Requirement: Stock no negativo
El sistema MUST impedir egresos que excedan el stock disponible, salvo una política explícita futura.

#### Scenario: Venta sin stock
- **WHEN** una operación intenta retirar más unidades de las disponibles
- **THEN** la transacción completa se rechaza sin cambios parciales