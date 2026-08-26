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
| Categoría-Atributo | Completo | `GET/POST/PUT/DELETE /api/v1/categorias-atributos` |
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
