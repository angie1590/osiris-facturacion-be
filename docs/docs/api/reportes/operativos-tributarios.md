---
id: operativos-tributarios
title: "Reportes: Operativos, Tributarios e Inventario"
sidebar_position: 3
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# Reportes: Operativos, Tributarios e Inventario

## `GET /api/v1/reportes/compras/por-proveedor`

Propósito: volumen de compras por proveedor, ordenado de mayor a menor.

Query params:

| Param | Tipo | Obligatorio |
|---|---|---|
| `fecha_inicio` | date | Sí |
| `fecha_fin` | date | Sí |
| `sucursal_id` | UUID | No |

Salida por fila:

- `proveedor_id`
- `razon_social`
- `total_compras`
- `cantidad_facturas`

---

## `GET /api/v1/reportes/sri/monitor-estados`

Propósito: monitorear documentos FE por estado SRI y tipo de documento.

Query params:

| Param | Tipo | Obligatorio |
|---|---|---|
| `fecha_inicio` | date | Sí |
| `fecha_fin` | date | Sí |
| `sucursal_id` | UUID | No |

<Tabs>
<TabItem value="response-monitor" label="Response 200">

```json
[
  { "estado": "AUTORIZADO", "tipo_documento": "FACTURA", "cantidad": 150 },
  { "estado": "RECHAZADO", "tipo_documento": "FACTURA", "cantidad": 5 },
  { "estado": "EN_COLA", "tipo_documento": "RETENCION", "cantidad": 2 }
]
```

</TabItem>
</Tabs>

---

## `GET /api/v1/reportes/impuestos/mensual`

Propósito: consolidado Pre-104 mensual.

Query params:

| Param | Tipo | Obligatorio |
|---|---|---|
| `mes` | int | Sí (`1..12`) |
| `anio` | int | Sí |
| `sucursal_id` | UUID | No |

Bloques de respuesta:

- `ventas` (base 0, base IVA, monto IVA, total, total_documentos)
- `compras` (idem)
- `retenciones_emitidas` (mapa por código SRI)
- `retenciones_recibidas` (mapa por código SRI)

---

## `GET /api/v1/reportes/inventario/valoracion`

Propósito: patrimonio de inventario con costo promedio vigente.

Salida:

- `patrimonio_total`
- `productos[]` con:
  - `producto_id`
  - `nombre`
  - `cantidad_actual`
  - `costo_promedio`
  - `valor_total`

---

## `GET /api/v1/reportes/inventario/kardex/{producto_id}`

Propósito: kárdex histórico NIIF por producto.

Query params:

| Param | Tipo | Obligatorio |
|---|---|---|
| `fecha_inicio` | date | No |
| `fecha_fin` | date | No |
| `sucursal_id` | UUID | No |

Regla default:

- si no se envían fechas:
  - `fecha_inicio = hoy - 1 año`
  - `fecha_fin = hoy`

Salida de movimientos:

- `fecha`
- `tipo_movimiento` (`INGRESO`, `EGRESO`, `VENTA`)
- `cantidad`
- `costo_unitario`
- `saldo_cantidad`

---

## `GET /api/v1/reportes/cartera/cobrar`

Propósito: saldos pendientes de CxC agrupados por cliente.

Reglas:

- incluye solo saldo `> 0`
- estados válidos: `PENDIENTE`, `PARCIAL`

---

## `GET /api/v1/reportes/cartera/pagar`

Propósito: saldos pendientes de CxP agrupados por proveedor.

Reglas:

- incluye solo saldo `> 0`
- estados válidos: `PENDIENTE`, `PARCIAL`

---

## `GET /api/v1/reportes/caja/cierre-diario`

Propósito: arqueo diario por cobros reales.

Query params:

| Param | Tipo | Obligatorio |
|---|---|---|
| `fecha` | date | No (default hoy) |
| `usuario_id` | UUID | No |
| `sucursal_id` | UUID | No |

Estructura:

- `dinero_liquido.total`
- `dinero_liquido.por_forma_pago[]`
- `credito_tributario.total_retenciones`

<Tabs>
<TabItem value="response-caja" label="Response 200">

```json
{
  "fecha": "2026-02-25",
  "usuario_id": null,
  "sucursal_id": null,
  "dinero_liquido": {
    "total": "150.00",
    "por_forma_pago": [
      { "forma_pago_sri": "EFECTIVO", "monto": "100.00" },
      { "forma_pago_sri": "TRANSFERENCIA", "monto": "50.00" }
    ]
  },
  "credito_tributario": {
    "total_retenciones": "10.00"
  }
}
```

</TabItem>
</Tabs>

## Recomendaciones de implementación frontend

1. Reusar un componente de filtros global:
   - rango fechas
   - sucursal
   - punto emisión
2. Mantener consistencia visual de montos (`2` decimales) y cantidades (`4` cuando aplique).
3. En kárdex, mostrar corrida de saldo con estilo de línea de tiempo.
