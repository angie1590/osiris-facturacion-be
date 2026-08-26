---
id: matriz-pantallas-endpoints
title: "Reportes: Matriz Pantallas ↔ Endpoints"
sidebar_position: 2
---

# Reportes: Matriz Pantallas ↔ Endpoints

Matriz de implementación frontend para dashboards y reportes del ERP.

## Matriz por pantalla

| Pantalla/Widget Front | Método + Endpoint | Query mínima | Payload mínimo | Success | Errores esperados |
|---|---|---|---|---|---|
| Tarjetas resumen comercial | `GET /api/v1/reportes/ventas/resumen` | `fecha_inicio`, `fecha_fin` | N/A | `200` JSON resumen | `400`, `422` |
| Ranking top productos | `GET /api/v1/reportes/ventas/top-productos` | opcional: `fecha_inicio`, `fecha_fin`, `limite` | N/A | `200` lista | `400`, `422` |
| Serie temporal ventas | `GET /api/v1/reportes/ventas/tendencias` | `fecha_inicio`, `fecha_fin`, `agrupacion` | N/A | `200` lista cronológica | `400`, `422` |
| Desempeño por vendedor | `GET /api/v1/reportes/ventas/por-vendedor` | opcional: `fecha_inicio`, `fecha_fin` | N/A | `200` lista | `400`, `422` |
| Rentabilidad por cliente | `GET /api/v1/reportes/rentabilidad/por-cliente` | `fecha_inicio`, `fecha_fin` | N/A | `200` lista | `400`, `422` |
| Rentabilidad por transacción | `GET /api/v1/reportes/rentabilidad/transacciones` | `fecha_inicio`, `fecha_fin` | N/A | `200` lista | `400`, `422` |
| Compras por proveedor | `GET /api/v1/reportes/compras/por-proveedor` | `fecha_inicio`, `fecha_fin` | N/A | `200` lista | `400`, `422` |
| Monitor estados SRI | `GET /api/v1/reportes/sri/monitor-estados` | `fecha_inicio`, `fecha_fin` | N/A | `200` lista | `400`, `422` |
| Pre-104 mensual | `GET /api/v1/reportes/impuestos/mensual` | `mes`, `anio` | N/A | `200` JSON consolidado | `400`, `422` |
| Valoración inventario | `GET /api/v1/reportes/inventario/valoracion` | N/A | N/A | `200` JSON | `400`, `422` |
| Kárdex histórico | `GET /api/v1/reportes/inventario/kardex/{producto_id}` | `producto_id`, opcional fechas | N/A | `200` JSON movimientos | `400`, `422` |
| Cartera por cobrar | `GET /api/v1/reportes/cartera/cobrar` | N/A | N/A | `200` lista | `400`, `422` |
| Cartera por pagar | `GET /api/v1/reportes/cartera/pagar` | N/A | N/A | `200` lista | `400`, `422` |
| Cierre diario caja | `GET /api/v1/reportes/caja/cierre-diario` | opcional: `fecha`, `usuario_id`, `sucursal_id` | N/A | `200` JSON cierre | `400`, `422` |

## Filtros recomendados por módulo

## Comercial

- `fecha_inicio`, `fecha_fin`
- `punto_emision_id` (cuando aplica)
- `sucursal_id` (cuando aplica)

## Tributario

- `mes`, `anio`
- `sucursal_id`

## Inventario

- `producto_id`
- `fecha_inicio`, `fecha_fin`
- `sucursal_id`

## Reglas UI críticas

1. Mostrar montos siempre con 2 decimales.
2. No asumir que todos los endpoints devuelven paginación; en reportes la mayoría devuelve listas directas.
3. En tendencias, conservar orden cronológico del backend para gráficas.
4. En rentabilidad, resaltar margen negativo para detección de pérdidas.
