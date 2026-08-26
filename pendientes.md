# Pendientes Para Siguiente Etapa

## API Inventario / Producto

1. Migrar `POST /api/v1/productos/{producto_id}/impuestos` para recibir payload en body JSON (actualmente usa query params).
2. Definir versión de transición para evitar ruptura de clientes existentes (`v1` query params, `v2` body JSON).
3. Evaluar endpoint dedicado para desasignar `Producto-Bodega` (hoy se puede dejar en cantidad `0`, pero no existe `DELETE` explícito de relación).

## Inventario y Reglas Contables (Post-MVP)

1. Definir política contable avanzada para anulaciones de movimientos confirmados:
   - tratamiento en cierre mensual,
   - trazabilidad de impacto financiero,
   - reglas de recosteo/capas para escenarios complejos.
2. Integrar esas reglas con el futuro módulo de contabilidad (asientos automáticos y reversos).
3. Formalizar política de anulación de compra/venta para escenario sin contabilidad:
   - **MVP actual recomendado**: reversar inventario y estado del documento, manteniendo trazabilidad en kárdex/auditoría.
   - **Siguiente etapa**: incluir reverso contable y definición explícita de impacto en valorización histórica.

## QA / Operación

1. Revisar estrategia de smoke tests actualmente marcados como `skipped` por entorno para su ejecución completa en pipeline dedicado.
