---
id: checklist-integracion-frontend
title: "Inventario: Checklist de Integración Frontend"
sidebar_position: 0
---

# Inventario: Checklist de Integración Frontend

Este documento consolida la auditoría funcional de la sección de inventario para implementación frontend en ERP ecuatoriano.

## Reglas Transversales (Operación Diaria)

- Mostrar por defecto registros activos (`only_active=true`) cuando el endpoint lo soporte.
- Tratar inactivos como borrado lógico; usarlos solo en vistas administrativas.
- Tratar montos y cantidades como `string decimal` en UI/estado local para no perder precisión.
- Para inventario físico, validar fracciones en frontend según `producto.permite_fracciones`.

## Checklist de Cobertura API (Frontend)

| Bloque | Estado | Cobertura |
|---|---|---|
| Categorías | Completo | `GET/POST/PUT/DELETE /api/v1/categorias` |
| Atributos | Completo | `GET/POST/PUT/DELETE /api/v1/atributos` |
| Categoría-Atributo legacy | Compatibilidad temporal | `GET /api/v1/categorias-atributos` deprecado y protegido por `ATRIBUTOS.leer`; POST/PUT/DELETE devuelven 410. Escrituras contextuales bajo `/api/v1/categorias/{id}/atributos`. |
| Catálogo administrativo de atributos | Completo | árbol, seleccionables, atributos efectivos/propios, asignación contextual, preview, override, backfill, baja y restauración |
| Unidades de atributo | Completo | `GET/POST /api/v1/unidades`, edición/reactivación/baja protegidas por uso y anotación confirmada en atributos numéricos |
| Casas Comerciales | Completo | `GET/POST/PUT/DELETE /api/v1/casas-comerciales` |
| Bodegas | Completo | `GET/POST/PUT/DELETE /api/v1/bodegas` + regla de bloqueo por stock/asignación |
| Productos (CRUD) | Completo | `GET/POST/PUT/DELETE /api/v1/productos` |
| Atributos por Producto | Completo | `PUT /api/v1/productos/{producto_id}/atributos` |
| Impuestos por Producto | Completo | `GET/POST/DELETE` de impuestos |
| Producto-Bodega | Completo | asignación, actualización y listados por producto/bodega |
| Stock disponible (consulta rápida) | Completo | `GET /api/v1/inventarios/stock-disponible` |
| Movimientos de inventario | Completo | crear, confirmar, anular, kardex, valoración |
| Transferencias entre bodegas | Completo | `POST /api/v1/inventarios/transferencias` |

## Reglas Críticas para UX/Validación

1. No permitir guardar cantidad fraccional si `permite_fracciones = false`.
2. No permitir stock positivo para productos de tipo `SERVICIO`.
3. En transferencias, bloquear origen y destino iguales.
4. En anulación de movimientos confirmados, advertir que el sistema ejecuta reverso automático de stock.
5. En eliminación de bodega, mostrar error de negocio cuando tenga:
   - productos asignados activos, o
   - stock materializado mayor a cero.

## Errores Funcionales Esperados (No Técnicos)

- `400`:
  - cantidad inválida/negativa,
  - no cumple regla de fracciones,
  - inventario insuficiente,
  - anulación inválida por estado.
- `404`:
  - producto/bodega/movimiento no encontrado.
- `409`:
  - intento de operar con bodega inactiva,
  - asignación duplicada producto-bodega.

## Catálogo de Categorías, Atributos y Unidades

- Leer jerarquía y selección desde `GET /api/v1/categorias/arbol` y `/seleccionables`; consumir `GET /api/v1/categorias/{id}/atributos-efectivos` y `/atributos-propios` para origen, override y unidad.
- Crear y asignar una definición en una sola operación con `POST /api/v1/atributos`; usar `/api/v1/atributos/previsualizar` cuando la operación requiera confirmar completitud o backfill. Las asignaciones contextuales se administran bajo `/api/v1/categorias/{id}/atributos` y su preview.
- Los defaults son valores numéricos separados de `unidad_id`; la UI añade el símbolo solo como sufijo de presentación. El backfill es opt-in y fill-only.
- Primera anotación de unidad requiere preview firmado y `confirmar_anotacion_unidad=true`; no convierte valores ni defaults. No cambiar una unidad A por B ni quitarla mediante PUT ordinario cuando existe historia. El undo de anotación usa `POST /api/v1/atributos/{id}/revertir` y verifica que el post-estado siga intacto.
- Tratar `ATTRIBUTE_UNIT_ANNOTATION_REQUIRES_CONFIRMATION`, `ATTRIBUTE_UNIT_CHANGE_REQUIRES_CONVERSION`, `ATTRIBUTE_UNIT_REMOVAL_REQUIRES_MIGRATION`, `UNIT_IN_USE` y `CATALOG_PREVIEW_STALE` como conflictos funcionales. No reintentar confirmaciones con un token o draft modificado.
- La unidad comercial del producto, su formulario, alta atómica y corte del puente de categorías permanecen fuera del alcance de este catálogo administrativo.
