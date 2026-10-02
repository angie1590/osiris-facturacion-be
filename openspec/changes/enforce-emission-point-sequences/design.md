## Context

`PuntoEmision.codigo` y `Sucursal.codigo` representan bloques de serie. `PuntoEmisionSecuencial` tiene clave única por punto/documento y se bloquea con `FOR UPDATE`; al crear el primer contador se inicializa con `PuntoEmision.secuencial_actual`, cuyo default es 1, y después se incrementa. La venta actualmente llama este mecanismo al crear incluso si queda BORRADOR. Además existe un endpoint `/siguiente` que confirma una reserva sin crear factura y un ajuste administrativo que puede saltar el correlativo.

## Goals / Non-Goals

**Goals:**
- La venta BORRADOR no consume secuencia. El número se asigna al emitir dentro de la transacción ya serializada por `Venta` y se revierte si inventario, CxC, snapshot o cola FE falla.
- Cada punto/doc mantiene contador independiente, con inicio explícito y formato exactamente `EEE-PPP-SSSSSSSSS`.
- Prevenir colisiones con índice único por empresa, punto y número formateado; no permitir desbordar nueve dígitos.
- Impedir reutilizar el mismo punto al cambiar la modalidad de su serie física/electrónica.
- Mantener un endpoint de lectura previa sin reserva; ninguna llamada de “preview” altera el contador.

**Non-Goals:**
- Numerar documentos físicos de venta no implementados en el sistema.
- Sincronizar la autorización formal de la serie con el portal SRI.
- Eliminar identificadores de correlativo de otros tipos documentales como retenciones/notas.
- Reconciliar automáticamente números emitidos fuera de Osiris.

## Decisions

1. **El contador persistido representa el último número emitido; el punto configura el siguiente inicial.** Si la configuración de punto dice 1, el contador de factura se crea en 0 y al emitir produce 1. Mantener un “próximo número” mutable crearía dos fuentes de verdad y facilitaría saltos.
2. **Consumir número al emitir, no al crear borrador.** `registrar_venta` guarda `secuencial_formateado = NULL` cuando hay punto; `emitir_venta` toma bloqueo y asigna el correlativo antes de crear el documento FE. La transacción ya contiene egreso/cartera/cola y cualquier error hace rollback del número y la venta de manera atómica.
3. **La ruta `POST .../siguiente` deja de reservar.** Se conserva compatibilidad de ruta pero devuelve un preview calculado bajo bloqueo sin incremento/commit; la venta no confía en ese valor y solo su propia emisión confirma el número. La asignación manual posterior al primer documento se rechaza; el punto debe configurarse correctamente antes de emitir. Los ajustes administrados fuera de rango se reemplazan por alta de punto/serie nueva.
4. **Un punto tiene modalidad inmutable (`FISICA` o `ELECTRONICA`).** Nueva modalidad se logra con un punto distinto; no se modifica una serie ya creada. Migración backfill usa modalidad de la empresa actual. Para excepciones de RIMPE/actividad excluida la modalidad de emisión efectiva sigue determinada por la estrategia tributaria y deberá coincidir con un punto electrónico autorizado.
5. **Restricción de unicidad compuesta en factura.** `(empresa_id, punto_emision_id, secuencial_formateado)` evita duplicados aun ante errores de aplicación y permite el mismo prefijo en empresas diferentes. Los registros legacy sin punto quedan fuera mediante NULL.
6. **Visualización.** API expone modalidad y próximo número esperado por punto/documento. La UI muestra claramente código de sucursal, punto, próximo formato completo y que la modalidad se configura creando un punto nuevo. Secuencial inicial sólo se establece en alta; no se edita después de emisión.

## Risks / Trade-offs

- [Cambios históricos ambiguos entre próximo/último número] → Migración conserva el valor de PuntoEmision como “próximo inicial” y crea el último emitido como valor menos uno; se documenta y se prueba con default 1 y valor personalizado.
- [Borradores existentes con secuencial asignado] → No renumerar silenciosamente; antes de desplegar, revisar drafts existentes y mantener sus números, inicializando los contadores por encima del máximo persistido.
- [Una excepción RIMPE electrónica no coincide con modalidad del punto] → El servicio valida modalidad efectiva; exige punto electrónico para factura electrónica y físico para nota física.
- [Pedidos concurrentes] → `SELECT FOR UPDATE`, una sola transacción de emisión y constraint único; prueba concurrente con PostgreSQL de CI donde esté disponible.
- [Downgrade pierde nueva modalidad] → Downgrade se bloquea si modalidad electrónica/física o datos de serie no pueden representarse en el esquema legacy.

## Migration Plan

1. Añadir modalidad al punto, backfill desde empresa, normalizar secuencial inicial para contador last-issued y añadir unicidad en factura.
2. Desplegar API/servicios/UI que asignan secuencial durante emisión; previews no consumen.
3. Reiniciar worker/API después de aplicar `alembic upgrade head`.
4. Revisar borradores ya numerados y configurar próximos iniciales autorizados por punto antes de habilitar emisión.
5. Rollback sólo tras validar que no hay series/modalidades o registros emitidos incompatibles; no bajar el head en producción automáticamente.

## Open Questions

- Los puntos legacy se backfillean con el modo de emisión actual de empresa; si una empresa emitía simultáneamente documentos físicos y electrónicos bajo el mismo punto, debe crearse y autorizarse una serie separada antes de activar la validación estricta.
- El ajuste manual del contador después de emitir queda bloqueado; la corrección operacional debe documentarse como nueva serie/punto con autorización SRI.
