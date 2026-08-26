---
id: ventas-ciclo-comercial
title: "Ventas: Ciclo Comercial, CxC y Retenciones Recibidas"
sidebar_position: 2
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# Ventas: Ciclo Comercial, CxC y Retenciones Recibidas

## Convenciones Generales

### Requisitos de consumo

- Header `Authorization: Bearer <token>`.
- Header `Content-Type: application/json`.
- Prefijo base de endpoints: `/api/v1`.
- Montos y cantidades siempre en decimal (string recomendado en frontend).

### Catálogos y enums

| Campo | Valores permitidos |
|---|---|
| tipo_identificacion_comprador | `RUC` \| `CEDULA` \| `PASAPORTE` |
| forma_pago | `EFECTIVO` \| `TARJETA` \| `TRANSFERENCIA` |
| tipo_emision | `ELECTRONICA` \| `NOTA_VENTA_FISICA` |
| regimen_emisor | `GENERAL` \| `RIMPE_EMPRENDEDOR` \| `RIMPE_NEGOCIO_POPULAR` |
| tipo_impuesto (detalle) | `IVA` \| `ICE` |
| codigo_impuesto_sri | `2` (IVA), `3` (ICE) |

## Reglas Tributarias Críticas (SRI)

### RIMPE Negocio Popular

- Puede emitir en `NOTA_VENTA_FISICA` o `ELECTRONICA`.
- Si el ítem no es actividad excluida (`es_actividad_excluida=false`), el IVA debe ser 0%.
- Si se intenta IVA > 0% en actividad no excluida, la API rechaza con `400`.

### Cálculo de impuestos por detalle

- Un detalle admite máximo 1 IVA y máximo 1 ICE.
- Base IVA se calcula sobre: `subtotal_sin_impuesto + ICE_detalle`.
- Totales de cabecera se calculan desde detalle y redondean a 2 decimales (`q2`).

## Estados de negocio

| Entidad | Estados |
|---|---|
| Venta | `BORRADOR` \| `EMITIDA` \| `ANULADA` |
| CxC | `PENDIENTE` \| `PARCIAL` \| `PAGADA` \| `ANULADA` |
| Retención recibida | `BORRADOR` \| `APLICADA` \| `ANULADA` |

---

POST /api/v1/ventas
Proposito: registra venta con detalle e impuestos snapshot. Por defecto emite automáticamente (`emitir_automaticamente=true`), ejecutando inventario + CxC + cola FE.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "cliente_id": "UUID | null",
  "empresa_id": "UUID | null",
  "punto_emision_id": "UUID | null",
  "fecha_emision": "2026-02-25",
  "bodega_id": "UUID | null",
  "tipo_identificacion_comprador": "RUC",
  "identificacion_comprador": "1790012345001",
  "forma_pago": "EFECTIVO",
  "tipo_emision": "ELECTRONICA",
  "regimen_emisor": "GENERAL",
  "usuario_auditoria": "user@dominio.com",
  "detalles": [
    {
      "producto_id": "UUID",
      "descripcion": "Producto A",
      "cantidad": "2.0000",
      "precio_unitario": "10.00",
      "descuento": "0.00",
      "es_actividad_excluida": false,
      "impuestos": [
        {
          "tipo_impuesto": "IVA",
          "codigo_impuesto_sri": "2",
          "codigo_porcentaje_sri": "4",
          "tarifa": "15.00"
        }
      ]
    }
  ]
}
```

</TabItem>
<TabItem value="response" label="Response 201">

```json
{
  "id": "UUID",
  "estado": "EMITIDA",
  "estado_sri": "ENVIADO",
  "subtotal_sin_impuestos": "20.00",
  "subtotal_15": "20.00",
  "monto_iva": "3.00",
  "valor_total": "23.00",
  "detalles": [
    {
      "producto_id": "UUID",
      "descripcion": "Producto A",
      "cantidad": "2.0000",
      "precio_unitario": "10.0000",
      "subtotal_sin_impuesto": "20.00",
      "impuestos": [
        {
          "tipo_impuesto": "IVA",
          "codigo_impuesto_sri": "2",
          "codigo_porcentaje_sri": "4",
          "tarifa": "15.00",
          "base_imponible": "20.00",
          "valor_impuesto": "3.00"
        }
      ]
    }
  ]
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla |
|---|---|---|
| detalles[].impuestos | array | máximo 1 IVA y 1 ICE |
| tipo_emision | enum | `NOTA_VENTA_FISICA` solo para RIMPE_NEGOCIO_POPULAR |
| es_actividad_excluida | bool | habilita excepción tributaria RIMPE para IVA > 0 |
| subtotal/monto/total | decimal | calculado por backend |
| emitir_automaticamente (query) | bool | `true` por defecto. Si `false`, guarda en `BORRADOR`. |

---

POST /api/v1/ventas/desde-productos
Proposito: registra venta usando snapshot de impuestos del producto. Por defecto también emite automáticamente.

| Diferencia clave | Descripción |
|---|---|
| `detalles[].impuestos` | No viene en payload, lo resuelve backend desde `ProductoImpuesto`. |

---

`GET /api/v1/ventas`
Proposito: listado paginado para bandeja comercial.

Query params:

| Param | Tipo | Descripción |
|---|---|---|
| `limit` | int | tamaño de página (default 50) |
| `offset` | int | desplazamiento (default 0) |
| `only_active` | bool | activos por defecto |
| `fecha_inicio` | date | filtro desde |
| `fecha_fin` | date | filtro hasta |
| `estado` | enum | `BORRADOR`, `EMITIDA`, `ANULADA` |
| `tipo_emision` | enum | `ELECTRONICA`, `NOTA_VENTA_FISICA` |
| `texto` | str | busca por identificación de comprador o número factura |

Campos principales por ítem:

- `fecha_emision`
- `cliente`
- `numero_factura`
- `valor_total`
- `estado`
- `estado_sri`
- `tipo_emision`

Response ejemplo:

```json
{
  "items": [
    {
      "id": "e2a18b13-3693-4bf3-8ff6-421b8e06e84a",
      "fecha_emision": "2026-02-25",
      "cliente_id": null,
      "cliente": "Consumidor Final",
      "numero_factura": "001-001-000000123",
      "valor_total": "23.00",
      "estado": "EMITIDA",
      "estado_sri": "ENVIADO",
      "tipo_emision": "ELECTRONICA"
    }
  ],
  "meta": {
    "total": 1,
    "limit": 50,
    "offset": 0,
    "next_offset": null,
    "prev_offset": null,
    "has_more": false,
    "page": 1,
    "page_count": 1
  }
}
```

---

`PUT /api/v1/ventas/{venta_id}`
`PATCH /api/v1/ventas/{venta_id}`
Proposito: actualiza cabecera de venta no emitida.

Reglas:
- Si la venta está `EMITIDA`, responde `400`.
- Si se intenta `NOTA_VENTA_FISICA` fuera de RIMPE_NEGOCIO_POPULAR, responde `400`.

---

`GET /api/v1/ventas/{venta_id}`
Proposito: obtiene detalle completo de venta (cabecera + detalles + snapshot de impuestos).

---

`POST /api/v1/ventas/{venta_id}/emitir`
Proposito: emite manualmente una venta en una única transacción (solo cuando fue creada en borrador con `emitir_automaticamente=false`):

1. Valida stock con lock pesimista.
2. Crea y confirma egreso de inventario.
3. Crea CxC inicial en estado `PENDIENTE`.
4. Cambia venta a `EMITIDA`.
5. Si `tipo_emision=ELECTRONICA`, encola documento SRI.

<Tabs>
<TabItem value="request-emitir" label="Request">

```json
{
  "usuario_auditoria": "user@dominio.com"
}
```

</TabItem>
</Tabs>

Errores frecuentes:

- `400`: venta ya emitida/anulada.
- `400`: stock insuficiente.
- `400`: ya existe CxC activa para la venta.

---

`POST /api/v1/ventas/{venta_id}/anular`
Proposito: anula venta emitida con reverso de inventario y cierre administrativo.

<Tabs>
<TabItem value="request-anular" label="Request">

```json
{
  "usuario_auditoria": "user@dominio.com",
  "confirmado_portal_sri": true,
  "motivo": "Anulada por error de digitación"
}
```

</TabItem>
</Tabs>

Reglas:

- Solo ventas `EMITIDA`.
- Si factura electrónica AUTORIZADA:
  - requiere `confirmado_portal_sri=true`,
  - requiere `motivo`.
- Si tiene cobros o retenciones aplicadas en CxC, no permite anular.
- Ejecuta reverso de inventario con movimiento `AJUSTE`.

---

`GET /api/v1/ventas/{venta_id}/fe-payload`
Proposito: devuelve payload FE-EC de la venta para diagnóstico/soporte.

---

POST /api/v1/retenciones-recibidas
Proposito: registra comprobante de retención recibida (BORRADOR).

Reglas tributarias:

- `numero_retencion`: formato `NNN-NNN-NNNNNNNNN`.
- Unicidad por `cliente_id + numero_retencion`.
- Código `1` (renta): base no puede superar subtotal general de venta.
- Código `2` (IVA): base debe ser exactamente el monto IVA de la venta.
- Si venta tiene IVA 0, no permite retención de IVA.

---

`GET /api/v1/retenciones-recibidas`
Proposito: listado paginado de retenciones recibidas para reportería operativa.

Query params:

| Param | Tipo | Descripción |
|---|---|---|
| `limit` | int | tamaño de página |
| `offset` | int | desplazamiento |
| `only_active` | bool | activos por defecto |
| `fecha_inicio` | date | filtro desde |
| `fecha_fin` | date | filtro hasta |
| `estado` | enum | `BORRADOR`, `APLICADA`, `ANULADA` |

Response ejemplo:

```json
{
  "items": [
    {
      "id": "86eead9b-6a53-4c03-a2f4-b9f67c6de3bb",
      "venta_id": "e2a18b13-3693-4bf3-8ff6-421b8e06e84a",
      "cliente_id": "d8586a7f-7a5b-4a9f-abd9-0e6ee84d3bcf",
      "numero_retencion": "001-001-000000123",
      "fecha_emision": "2026-02-25",
      "estado": "APLICADA",
      "total_retenido": "10.00"
    }
  ],
  "meta": {
    "total": 1,
    "limit": 50,
    "offset": 0,
    "next_offset": null,
    "prev_offset": null,
    "has_more": false,
    "page": 1,
    "page_count": 1
  }
}
```

---

`GET /api/v1/retenciones-recibidas/{retencion_id}`
Proposito: obtiene detalle completo de una retención recibida.

---

`POST /api/v1/retenciones-recibidas/{retencion_id}/aplicar`
Proposito: aplica retención en CxC (descuenta saldo pendiente).

Reglas:

- Solo estado `BORRADOR`.
- Lock pesimista de CxC para concurrencia.
- Si retención supera saldo, error.

---

`POST /api/v1/retenciones-recibidas/{retencion_id}/anular`
Proposito: anula retención aplicada y revierte efecto en CxC.

Request:
```json
{
  "motivo": "Valor mal digitado",
  "usuario_auditoria": "user@dominio.com"
}
```

Reglas:

- Solo estado `APLICADA`.
- Motivo obligatorio.
- Registra historial de estado de retención.

---

`GET /api/v1/cxc/{venta_id}`
Proposito: obtiene CxC asociada a una venta.

---

`GET /api/v1/cxc`
Proposito: listado paginado general de cuentas por cobrar.

Query params:

| Param | Tipo | Descripción |
|---|---|---|
| `limit` | int | tamaño de página |
| `offset` | int | desplazamiento |
| `only_active` | bool | activos por defecto |
| `estado` | enum | `PENDIENTE`, `PARCIAL`, `PAGADA`, `ANULADA` |
| `texto` | str | busca por identificación del comprador o número de factura |

Response ejemplo:

```json
{
  "items": [
    {
      "id": "5e0d3ba5-0b57-4fd5-9e8f-5dd394dbf4de",
      "venta_id": "e2a18b13-3693-4bf3-8ff6-421b8e06e84a",
      "cliente_id": null,
      "cliente": "Consumidor Final",
      "numero_factura": "001-001-000000123",
      "fecha_emision": "2026-02-25",
      "valor_total_factura": "23.00",
      "valor_retenido": "0.00",
      "pagos_acumulados": "0.00",
      "saldo_pendiente": "23.00",
      "estado": "PENDIENTE"
    }
  ],
  "meta": {
    "total": 1,
    "limit": 50,
    "offset": 0,
    "next_offset": null,
    "prev_offset": null,
    "has_more": false,
    "page": 1,
    "page_count": 1
  }
}
```

Campos principales por ítem:

- `fecha_emision`
- `cliente`
- `numero_factura`
- `valor_total_factura`
- `valor_retenido`
- `pagos_acumulados`
- `saldo_pendiente`
- `estado`

---

`POST /api/v1/cxc/{venta_id}/pagos`
Proposito: registra pago en CxC.

<Tabs>
<TabItem value="request-pago" label="Request">

```json
{
  "monto": "50.00",
  "fecha": "2026-02-25",
  "forma_pago_sri": "EFECTIVO",
  "usuario_auditoria": "user@dominio.com"
}
```

</TabItem>
</Tabs>

Reglas:

- Lock pesimista de CxC.
- No permite sobrepago (`monto > saldo_pendiente`).
- Recalcula saldo y estado (`PARCIAL`/`PAGADA`).

## Errores Comunes para Frontend

| Endpoint | HTTP | Caso |
|---|---|---|
| `POST /api/v1/ventas` | 400 | Regla RIMPE/IVA inválida, producto sin impuestos snapshot válido |
| `POST /api/v1/ventas/{id}/emitir` | 400 | Stock insuficiente, estado inválido |
| `POST /api/v1/ventas/{id}/anular` | 400 | Sin confirmación SRI o con cobros registrados |
| `POST /api/v1/retenciones-recibidas` | 400 | Número duplicado o reglas de base imponible inválidas |
| `POST /api/v1/cxc/{venta_id}/pagos` | 400 | Sobrepago |

## Nota de Implementación (comportamiento actual)

- Flujo oficial: `POST /ventas` y `POST /ventas/desde-productos` emiten automáticamente por defecto.
- Modo asistido opcional: usar `emitir_automaticamente=false` para dejar `BORRADOR` y emitir luego con `POST /ventas/{id}/emitir`.
