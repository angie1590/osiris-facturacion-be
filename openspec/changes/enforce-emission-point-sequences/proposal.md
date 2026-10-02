## Why

La serie debe ser trazable por establecimiento y punto, y el correlativo no debe consumirse al guardar un borrador ni reservarse fuera de la emisión transaccional. Hoy el contador puede iniciar en `000000002`, se puede reservar por un endpoint independiente y no se distingue una serie física de una electrónica.

## What Changes

- Formalizar el formato de factura `EEE-PPP-SSSSSSSSS`, validando establecimiento/punto de tres dígitos y secuencial de nueve dígitos.
- Interpretar el secuencial configurado en un punto nuevo como el siguiente número que se emitirá; emitir por primera vez `000000001` por defecto.
- Asignar el correlativo solamente al emitir la venta, dentro de la transacción que confirma inventario, CxC y cola FE; borradores no consumen números y un rollback revierte el contador.
- Asegurar unicidad por punto y formato emitido; rechazar overflow y ajustes manuales que creen saltos o puedan duplicar documentos.
- Registrar modalidad física/electrónica inmutable al crear el punto; para cambiar modalidad se crea un punto/serie nueva con un correlativo inicial autorizado. Las secuencias permanecen independientes por punto y tipo documental.
- Retirar la reserva separada del siguiente secuencial como mecanismo de emisión; ofrecer una consulta no consumidora para visualizar el próximo número.

No incluye emisión de factura física actualmente no modelada, integración con autorizaciones del portal SRI ni migración automática de series de otro sistema. La configuración inicial/importada debe indicar el último emitido o el próximo autorizado de forma inequívoca.

## Capabilities

### New Capabilities
- `emission-point-sequences`: Configuración de modalidades por punto, formato de serie, correlatividad transaccional y control de cambios de modalidad.

### Modified Capabilities

## Impact

- Backend: modelos, migraciones Alembic, API de puntos, servicios de secuencias, creación/emisión de ventas y snapshots.
- Frontend: formulario de puntos de emisión y visualización/ajuste del próximo número disponible.
- Inventario/CxC: el movimiento de egreso y la cuenta por cobrar permanecen en la transacción de emisión; no cambian sus reglas.
- SRI: factura electrónica se encola con el número ya confirmado en venta; la serie no se solicita aparte.
- Multiempresa: unicidad se limita a la identidad empresa/punto/serie, sin bloquear números homónimos en empresas distintas.
