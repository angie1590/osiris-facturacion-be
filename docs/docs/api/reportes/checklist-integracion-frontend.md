---
id: checklist-integracion-frontend
title: "Reportes: Checklist de Integración Frontend"
sidebar_position: 1
---

# Reportes: Checklist de Integración Frontend

Este documento cubre el módulo `src/osiris/modules/reportes` (`/api/v1/reportes`).

## Cobertura de Endpoints (estado actual)

| Bloque | Endpoint | Estado |
|---|---|---|
| Ventas | `GET /api/v1/reportes/ventas/resumen` | Implementado |
| Ventas | `GET /api/v1/reportes/ventas/top-productos` | Implementado |
| Ventas | `GET /api/v1/reportes/ventas/tendencias` | Implementado |
| Ventas | `GET /api/v1/reportes/ventas/por-vendedor` | Implementado |
| Rentabilidad | `GET /api/v1/reportes/rentabilidad/por-cliente` | Implementado |
| Rentabilidad | `GET /api/v1/reportes/rentabilidad/transacciones` | Implementado |
| Compras | `GET /api/v1/reportes/compras/por-proveedor` | Implementado |
| SRI | `GET /api/v1/reportes/sri/monitor-estados` | Implementado |
| Tributario | `GET /api/v1/reportes/impuestos/mensual` | Implementado |
| Inventario | `GET /api/v1/reportes/inventario/valoracion` | Implementado |
| Inventario | `GET /api/v1/reportes/inventario/kardex/{producto_id}` | Implementado |
| Cartera | `GET /api/v1/reportes/cartera/cobrar` | Implementado |
| Cartera | `GET /api/v1/reportes/cartera/pagar` | Implementado |
| Caja | `GET /api/v1/reportes/caja/cierre-diario` | Implementado |

## Reglas transversales del módulo

1. Base monetaria: `Decimal` con redondeo a 2 decimales.
2. Por defecto se excluyen ventas/compras anuladas en agregaciones.
3. Filtros de multi-sucursal aplican por relación real de transacción (no por usuario).
4. Errores comunes:
   - `400`: parámetros inconsistentes
   - `422`: error de validación de query params

## Checklist UI recomendado

- Dashboard comercial:
  - resumen ventas
  - tendencias
  - top productos
  - por vendedor
- Dashboard financiero:
  - rentabilidad por cliente/transacción
  - cartera cobrar/pagar
  - cierre diario de caja
- Dashboard fiscal:
  - pre-104 mensual
  - monitor SRI por estado/tipo de documento
- Dashboard inventario:
  - valoración total
  - kárdex histórico por producto

## Filtros clave que debe exponer frontend

- `fecha_inicio`, `fecha_fin`
- `sucursal_id` donde aplique
- `punto_emision_id` donde aplique
- `agrupacion` en tendencias (`DIARIA`, `MENSUAL`, `ANUAL`)

## Referencia de implementación por pantalla

Para una guía operativa por widget/pantalla:

- `API > Reportes > Reportes: Matriz Pantallas ↔ Endpoints`
