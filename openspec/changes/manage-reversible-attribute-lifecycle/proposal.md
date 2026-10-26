## Why

Un error al nombrar o tipar un atributo reutilizado puede afectar formularios, asignaciones por categoría y valores de productos. El CRUD actual permite actualizar y dar de baja, pero una conversión ya aplicada no conserva un estado completo que pueda restaurarse con seguridad.

## What Changes

- Formalizar edición auditada de la definición completa de Atributo conservando su ID.
- Añadir una previsualización de conversiones con conteos de valores convertibles, remapeos pendientes y asignaciones/valores alcanzados.
- Guardar snapshots transaccionales de definición, asignaciones por categoría y valores EAV antes/después de editar, convertir o dar de baja.
- Permitir revertir la operación más reciente solo si la definición y los datos actuales coinciden con el estado posterior capturado; bloquear con `409` ante cambios concurrentes, cambios posteriores de EAV, asignaciones nuevas o remapeos ya resueltos.
- Completar baja lógica reversible de Atributo desactivando sus asignaciones y valores activos sin borrar historial; bloquear si existen remapeos pendientes que no pueden reactivarse con seguridad.
- Añadir acción explícita de reactivación/reversión para Atributo inactivo, usando el mismo ID y auditoría.
- Mostrar en la UI común de Atributos edición, vista previa, confirmación de cambios destructivos, baja/reactivación y explicación de conflictos.

## Capabilities

### New Capabilities

- `reversible-attribute-lifecycle`: historial transaccional, previsualización, revertibilidad comprobada y baja lógica segura de Atributo.
- `attribute-lifecycle-ui`: formularios comunes de edición, vista previa del impacto y acciones de restauración/baja.

### Modified Capabilities

Ninguna spec principal existente; los cambios previos de categorías/atributos están archivados y no se alterarán.

## Impact

- Backend: `inventario/atributo`, asignaciones `categoria_atributo`, valores EAV y remapeos de producto; nueva tabla Alembic de snapshots, endpoints de previsualización/reversión/reactivación, pruebas SQLite y PostgreSQL.
- Frontend: ruta existente `/atributos` y componentes `src/components/shared` y `src/components/ui`; no se crearán componentes privados de módulo.
- Inventario: solo metadatos y valores EAV; no cambia cantidad, costo, stock, categorías de producto ni movimientos.
- Compras/ventas/SRI: no se recalculan snapshots tributarios ni documentos históricos.
- No objetivos: editor de valores EAV en producto, fusión/renombrado masivo, borrado físico, historial general de auditoría navegable o cambio de obligatoriedad por categoría desde este CRUD.