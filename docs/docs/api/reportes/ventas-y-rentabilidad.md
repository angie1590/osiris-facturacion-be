---
id: ventas-y-rentabilidad
title: "Reportes: Ventas y Rentabilidad"
sidebar_position: 2
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# Reportes: Ventas y Rentabilidad

## `GET /api/v1/reportes/ventas/resumen`

Propósito: resumen agregado del período (excluye ventas anuladas).

Query params:

| Param | Tipo | Obligatorio |
|---|---|---|
| `fecha_inicio` | date | Sí |
| `fecha_fin` | date | Sí |
| `punto_emision_id` | UUID | No |
| `sucursal_id` | UUID | No |

Campos de salida:

- `subtotal_0`
- `subtotal_12`
- `monto_iva`
- `total`
- `total_ventas`

---

## `GET /api/v1/reportes/ventas/top-productos`

Propósito: ranking de productos vendidos con ganancia bruta estimada.

Query params:

| Param | Tipo | Obligatorio |
|---|---|---|
| `fecha_inicio` | date | No |
| `fecha_fin` | date | No |
| `punto_emision_id` | UUID | No |
| `limite` | int | No (`1..100`, default `10`) |

Regla de cálculo:

- `ganancia_bruta_estimada = total_dolares_vendido - (costo_promedio * cantidad_vendida)`

---

## `GET /api/v1/reportes/ventas/tendencias`

Propósito: serie de tiempo de ventas.

Query params:

| Param | Tipo | Obligatorio | Valores |
|---|---|---|---|
| `fecha_inicio` | date | Sí | - |
| `fecha_fin` | date | Sí | - |
| `agrupacion` | enum | No | `DIARIA`, `MENSUAL`, `ANUAL` |

<Tabs>
<TabItem value="response-tendencias" label="Response 200">

```json
[
  {
    "periodo": "2026-02-01",
    "total": "120.00",
    "total_ventas": 3
  },
  {
    "periodo": "2026-02-02",
    "total": "50.00",
    "total_ventas": 1
  }
]
```

</TabItem>
</Tabs>

---

## `GET /api/v1/reportes/ventas/por-vendedor`

Propósito: ventas agrupadas por usuario creador de la factura.

Query params:

| Param | Tipo | Obligatorio |
|---|---|---|
| `fecha_inicio` | date | No |
| `fecha_fin` | date | No |

Salida:

- `usuario_id`
- `vendedor`
- `total_vendido`
- `facturas_emitidas`

---

## `GET /api/v1/reportes/rentabilidad/por-cliente`

Propósito: utilidad y margen por cliente.

Query params:

| Param | Tipo | Obligatorio |
|---|---|---|
| `fecha_inicio` | date | Sí |
| `fecha_fin` | date | Sí |

Reglas:

- costo histórico se calcula desde egresos confirmados de inventario vinculados a la venta.
- `margen_porcentual = (utilidad_bruta_dolares / total_vendido) * 100`

---

## `GET /api/v1/reportes/rentabilidad/transacciones`

Propósito: utilidad por factura individual.

Query params:

| Param | Tipo | Obligatorio |
|---|---|---|
| `fecha_inicio` | date | Sí |
| `fecha_fin` | date | Sí |

<Tabs>
<TabItem value="response-rentabilidad" label="Response 200">

```json
[
  {
    "venta_id": "e2a18b13-3693-4bf3-8ff6-421b8e06e84a",
    "cliente_id": null,
    "fecha_emision": "2026-02-25",
    "subtotal_venta": "100.00",
    "costo_historico_total": "60.00",
    "utilidad_bruta_dolares": "40.00",
    "margen_porcentual": "40.00"
  }
]
```

</TabItem>
</Tabs>

## Manejo recomendado en frontend

1. Mostrar valores monetarios con 2 decimales.
2. Mostrar margen negativo en rojo cuando sea `< 0`.
3. Permitir exportación CSV/Excel desde la grilla (cliente/transacción).
