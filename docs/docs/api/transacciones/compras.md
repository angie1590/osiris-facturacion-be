---
id: compras
title: "Compras"
sidebar_position: 1
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# Compras

## Convenciones Generales

### Requisitos de consumo

- Header `Authorization: Bearer <token>` en ambientes con seguridad habilitada.
- Header `Content-Type: application/json`.
- Todos los endpoints de esta pagina operan bajo prefijo `/api/v1`.

### Catalogos y enums

| Campo | Valores permitidos |
|---|---|
| forma_pago (FormaPagoSRI) | `EFECTIVO` \| `TARJETA` \| `TRANSFERENCIA` |
| tipo_identificacion_proveedor (TipoIdentificacionSRI) | `RUC` \| `CEDULA` \| `PASAPORTE` |
| sustento_tributario (SustentoTributarioSRI) | `01` \| `02` \| `05` |
| tipo_impuesto (TipoImpuestoMVP) | `IVA` \| `ICE` |
| tipo (TipoRetencionSRI) | `IVA` \| `RENTA` |

### Reglas tributarias transversales

- Un detalle de compra permite maximo 1 IVA y maximo 1 ICE.
- Si `tipo_impuesto=IVA`, `codigo_impuesto_sri` debe ser `"2"`.
- Si `tipo_impuesto=ICE`, `codigo_impuesto_sri` debe ser `"3"`.
- El IVA del detalle se calcula sobre `(subtotal_sin_impuesto + ICE_detalle)`.
- Los montos monetarios se redondean con precision `q2` (2 decimales).

### Estados de negocio

| Entidad | Flujo |
|---|---|
| Compra | `BORRADOR -> REGISTRADA -> ANULADA` |
| Retencion emitida | `REGISTRADA -> EMITIDA` o `REGISTRADA -> ENCOLADA` |
| CxP | `PENDIENTE -> PARCIAL -> PAGADA` |

Al registrar compra:
- Se crea y confirma un movimiento de inventario `INGRESO`.
- Se crea la CxP inicial en estado `PENDIENTE`.

Al anular compra:
- Se crea movimiento de reversa `EGRESO` con referencia `ANULACION_COMPRA:{id}`.

### Errores comunes

| Endpoint | HTTP | Caso |
|---|---|---|
| `POST /api/v1/compras` | 400 | Bodega no resoluble o reglas de impuestos invalidas. |
| `POST /api/v1/compras/desde-productos` | 404 | Producto inexistente o inactivo. |
| `PUT /api/v1/compras/{compra_id}` | 400 | Compra en estado `REGISTRADA`. |
| `POST /api/v1/compras/{compra_id}/anular` | 400 | No existe movimiento `INGRESO` confirmado para revertir. |
| `GET /api/v1/compras/{compra_id}/sugerir-retencion` | 404/400 | Compra/plantilla no existe o plantilla sin detalles. |
| `POST /api/v1/compras/{compra_id}/retenciones` | 400 | Ya existe retencion activa para la compra. |
| `POST /api/v1/retenciones/{retencion_id}/emitir` | 400 | Retencion ANULADA o excede saldo de CxP. |

### Alcance del modulo (API actual)

- En el router actual de compras no existen `GET /api/v1/compras` ni `GET /api/v1/compras/{id}`.

POST /api/v1/compras
Proposito: Registra una compra y la deja en estado REGISTRADA. Calcula subtotales e impuestos a partir de los detalles, crea CxP inicial y orquesta un ingreso a inventario (movimiento INGRESO) en la bodega indicada o en la unica bodega activa.

<Tabs>
<TabItem value="request" label="Request">

Body (JSON):
```json
{
  "sucursal_id": "UUID | null",
  "proveedor_id": "UUID",
  "secuencial_factura": "001-001-000000123",
  "autorizacion_sri": "1234567890123456789012345678901234567",
  "fecha_emision": "2026-02-24",
  "bodega_id": "UUID | null",
  "sustento_tributario": "01",
  "tipo_identificacion_proveedor": "RUC",
  "identificacion_proveedor": "1790012345001",
  "forma_pago": "TRANSFERENCIA",
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

Body (JSON):
```json
{
  "id": "UUID",
  "sucursal_id": "UUID | null",
  "proveedor_id": "UUID",
  "secuencial_factura": "001-001-000000123",
  "autorizacion_sri": "1234567890123456789012345678901234567",
  "fecha_emision": "2026-02-24",
  "sustento_tributario": "01",
  "tipo_identificacion_proveedor": "RUC",
  "identificacion_proveedor": "1790012345001",
  "forma_pago": "TRANSFERENCIA",
  "subtotal_sin_impuestos": "20.00",
  "subtotal_12": "0.00",
  "subtotal_15": "20.00",
  "subtotal_0": "0.00",
  "subtotal_no_objeto": "0.00",
  "monto_iva": "3.00",
  "monto_ice": "0.00",
  "valor_total": "23.00",
  "estado": "REGISTRADA",
  "creado_en": "2026-02-24T10:00:00",
  "actualizado_en": "2026-02-24T10:00:00"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| sucursal_id | UUID \| null | Opcional | Sucursal asociada a la compra. |
| proveedor_id | UUID | Requerido | Proveedor de la compra. |
| secuencial_factura | string | Regex ^\d{3}-\d{3}-\d{9}$ | Secuencial SRI de la factura. |
| autorizacion_sri | string | Regex ^\d{37}$ o ^\d{49}$ | Autorizacion SRI. |
| fecha_emision | date | Default hoy | Fecha de emision. |
| bodega_id | UUID \| null | Si es null y hay una sola bodega activa, se usa esa; si hay mas de una, error 400 | Bodega destino del ingreso de inventario. |
| detalles | array | Min 1 | Lineas de compra con impuestos. |
| detalles[].impuestos | array | Max 1 IVA y max 1 ICE por detalle | Validacion por detalle. |
| forma_pago | enum | EFECTIVO/TARJETA/TRANSFERENCIA | Forma de pago SRI. |
| subtotal_* / monto_* / valor_total | decimal | Computados desde detalles | Totales calculados por backend, con redondeo q2. |
| estado | string | REGISTRADA | La compra se registra y no queda en borrador. |
| inventario | interno | Movimiento INGRESO confirmado | Se crea y confirma movimiento de inventario por detalle. |
| cxp | interno | CxP PENDIENTE | Se crea cuenta por pagar con saldo total. |

---

POST /api/v1/compras/desde-productos
Proposito: Registra una compra a partir del catalogo de productos. Para cada detalle toma el snapshot de impuestos del producto (solo IVA/ICE del catalogo MVP) y luego sigue el mismo flujo de registro: calculo de totales, CxP e ingreso a inventario.

<Tabs>
<TabItem value="request" label="Request">

Body (JSON):
```json
{
  "sucursal_id": "UUID | null",
  "proveedor_id": "UUID",
  "secuencial_factura": "001-001-000000456",
  "autorizacion_sri": "1234567890123456789012345678901234567890123456789",
  "fecha_emision": "2026-02-24",
  "bodega_id": "UUID | null",
  "sustento_tributario": "01",
  "tipo_identificacion_proveedor": "RUC",
  "identificacion_proveedor": "1790012345001",
  "forma_pago": "EFECTIVO",
  "usuario_auditoria": "user@dominio.com",
  "detalles": [
    {
      "producto_id": "UUID",
      "descripcion": "Producto B",
      "cantidad": "5.0000",
      "precio_unitario": "4.50",
      "descuento": "0.00",
      "es_actividad_excluida": false
    }
  ]
}
```

</TabItem>
<TabItem value="response" label="Response 201">

Body (JSON):
```json
{
  "id": "UUID",
  "sucursal_id": "UUID | null",
  "proveedor_id": "UUID",
  "secuencial_factura": "001-001-000000456",
  "autorizacion_sri": "1234567890123456789012345678901234567890123456789",
  "fecha_emision": "2026-02-24",
  "sustento_tributario": "01",
  "tipo_identificacion_proveedor": "RUC",
  "identificacion_proveedor": "1790012345001",
  "forma_pago": "EFECTIVO",
  "subtotal_sin_impuestos": "22.50",
  "subtotal_12": "0.00",
  "subtotal_15": "22.50",
  "subtotal_0": "0.00",
  "subtotal_no_objeto": "0.00",
  "monto_iva": "3.38",
  "monto_ice": "0.00",
  "valor_total": "25.88",
  "estado": "REGISTRADA",
  "creado_en": "2026-02-24T10:05:00",
  "actualizado_en": "2026-02-24T10:05:00"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| detalles[].producto_id | UUID | Debe existir y estar activo | Producto del catalogo. |
| impuestos por producto | interno | Solo IVA/ICE (codigo_impuesto_sri 2 o 3) | Snapshot de impuestos del producto; si hay impuestos no compatibles, error 400. |
| detalles | array | Sin impuestos en payload | El backend inyecta impuestos a partir del producto. |
| resto de campos | ver endpoint anterior | Igual a /api/v1/compras | Mismas reglas de registro, inventario y CxP. |

---

PUT /api/v1/compras/\{compra_id\}
Proposito: Actualiza datos de cabecera de la compra solo si no esta en estado REGISTRADA. Si esta REGISTRADA, solo se permite anular.

<Tabs>
<TabItem value="request" label="Request">

Path params:
- compra_id (UUID)

Body (JSON):
```json
{
  "sucursal_id": "UUID | null",
  "secuencial_factura": "001-001-000000999",
  "autorizacion_sri": "1234567890123456789012345678901234567",
  "fecha_emision": "2026-02-24",
  "sustento_tributario": "01",
  "tipo_identificacion_proveedor": "RUC",
  "identificacion_proveedor": "1790012345001",
  "forma_pago": "TRANSFERENCIA",
  "usuario_auditoria": "user@dominio.com"
}
```

</TabItem>
<TabItem value="response" label="Response 200">

Body (JSON):
```json
{
  "id": "UUID",
  "sucursal_id": "UUID | null",
  "proveedor_id": "UUID",
  "secuencial_factura": "001-001-000000999",
  "autorizacion_sri": "1234567890123456789012345678901234567",
  "fecha_emision": "2026-02-24",
  "sustento_tributario": "01",
  "tipo_identificacion_proveedor": "RUC",
  "identificacion_proveedor": "1790012345001",
  "forma_pago": "TRANSFERENCIA",
  "subtotal_sin_impuestos": "20.00",
  "subtotal_12": "0.00",
  "subtotal_15": "20.00",
  "subtotal_0": "0.00",
  "subtotal_no_objeto": "0.00",
  "monto_iva": "3.00",
  "monto_ice": "0.00",
  "valor_total": "23.00",
  "estado": "BORRADOR",
  "creado_en": "2026-02-24T10:00:00",
  "actualizado_en": "2026-02-24T10:10:00"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| compra_id | UUID | Requerido | Identificador de la compra. |
| estado | string | Si es REGISTRADA no permite editar | Solo compras no registradas se actualizan. |
| usuario_auditoria | string | Requerido | Auditoria del cambio. |

---

POST /api/v1/compras/\{compra_id\}/anular
Proposito: Anula una compra y deja el estado en ANULADA. Es el flujo permitido cuando la compra ya esta REGISTRADA. Automaticamente orquesta la reversion del inventario creando un movimiento EGRESO que descuenta las cantidades ingresadas originalmente.

<Tabs>
<TabItem value="request" label="Request">

Path params:
- compra_id (UUID)

Body (JSON):
```json
{
  "usuario_auditoria": "user@dominio.com"
}
```

</TabItem>
<TabItem value="response" label="Response 200">

Body (JSON):
```json
{
  "id": "UUID",
  "sucursal_id": "UUID | null",
  "proveedor_id": "UUID",
  "secuencial_factura": "001-001-000000123",
  "autorizacion_sri": "1234567890123456789012345678901234567",
  "fecha_emision": "2026-02-24",
  "sustento_tributario": "01",
  "tipo_identificacion_proveedor": "RUC",
  "identificacion_proveedor": "1790012345001",
  "forma_pago": "TRANSFERENCIA",
  "subtotal_sin_impuestos": "20.00",
  "subtotal_12": "0.00",
  "subtotal_15": "20.00",
  "subtotal_0": "0.00",
  "subtotal_no_objeto": "0.00",
  "monto_iva": "3.00",
  "monto_ice": "0.00",
  "valor_total": "23.00",
  "estado": "ANULADA",
  "creado_en": "2026-02-24T10:00:00",
  "actualizado_en": "2026-02-24T10:20:00"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| compra_id | UUID | Requerido | Compra a anular. |
| usuario_auditoria | string | Requerido | Auditoria de la anulacion. |
| estado | string | ANULADA | Estado final tras la anulacion. |
| reversion_inventario | interno | Movimiento EGRESO confirmado automaticamente | Busca el movimiento INGRESO original (referencia_documento COMPRA:\{compra_id\}) y crea un EGRESO espejo (referencia_documento ANULACION_COMPRA:\{compra_id\}) para revertir las cantidades. Si no existe el movimiento de ingreso confirmado, error 400. |

---

GET /api/v1/compras/\{compra_id\}/sugerir-retencion
Proposito: Sugiere una retencion para la compra usando ValidacionImpuestosSRIStrategy. La base de IVA se calcula desde monto_iva y la base de renta desde subtotal_sin_impuestos.

<Tabs>
<TabItem value="request" label="Request">

Path params:
- compra_id (UUID)

</TabItem>
<TabItem value="response" label="Response 200">

Body (JSON):
```json
{
  "compra_id": "UUID",
  "plantilla_id": "UUID",
  "proveedor_id": "UUID | null",
  "detalles": [
    {
      "codigo_retencion_sri": "332",
      "tipo": "IVA",
      "porcentaje": "30.00",
      "base_calculo": "3.00",
      "valor_retenido": "0.90"
    },
    {
      "codigo_retencion_sri": "332",
      "tipo": "RENTA",
      "porcentaje": "1.00",
      "base_calculo": "20.00",
      "valor_retenido": "0.20"
    }
  ],
  "total_retenido": "1.10"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| plantilla_id | UUID | Proveedor o global | Si no hay plantilla, error 404. |
| detalles[].tipo | string | IVA o RENTA | Determina estrategia de base. |
| detalles[].base_calculo | decimal | Strategy: IVA usa monto_iva; RENTA usa subtotal_sin_impuestos | Base para calcular valor retenido. |
| detalles[].valor_retenido | decimal | base_calculo * porcentaje / 100 | Calculado por backend con redondeo q2. |
| total_retenido | decimal | Suma de detalles | Total sugerido. |

---

POST /api/v1/compras/\{compra_id\}/guardar-plantilla-retencion
Proposito: Guarda una plantilla de retencion a partir de la retencion digitada. Si es global o por proveedor, inactiva las plantillas anteriores y crea una nueva con sus detalles.

<Tabs>
<TabItem value="request" label="Request">

Path params:
- compra_id (UUID)

Body (JSON):
```json
{
  "usuario_auditoria": "user@dominio.com",
  "nombre": "Plantilla Retencion",
  "es_global": false,
  "detalles": [
    {
      "codigo_retencion_sri": "332",
      "tipo": "IVA",
      "porcentaje": "30.00"
    }
  ]
}
```

</TabItem>
<TabItem value="response" label="Response 200">

Body (JSON):
```json
{
  "id": "UUID",
  "proveedor_id": "UUID | null",
  "nombre": "Plantilla Retencion",
  "es_global": false,
  "detalles": [
    {
      "id": "UUID",
      "codigo_retencion_sri": "332",
      "tipo": "IVA",
      "porcentaje": "30.00"
    }
  ]
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| es_global | boolean | Si true, plantilla sin proveedor | Inactiva plantilla global anterior. |
| proveedor_id | UUID \| null | Si es_global=false, usa proveedor de compra | Se guarda la relacion con proveedor. |
| detalles[].porcentaje | decimal | Normalizado a q2 | Porcentaje de retencion. |

---

POST /api/v1/compras/\{compra_id\}/retenciones
Proposito: Registra una retencion emitida para la compra y la encola automaticamente a SRI (encolar_sri=true). Valida que no exista otra retencion activa por compra.

<Tabs>
<TabItem value="request" label="Request">

Path params:
- compra_id (UUID)

Body (JSON):
```json
{
  "fecha_emision": "2026-02-24",
  "usuario_auditoria": "user@dominio.com",
  "detalles": [
    {
      "codigo_retencion_sri": "332",
      "tipo": "IVA",
      "porcentaje": "30.00",
      "base_calculo": "3.00"
    }
  ]
}
```

</TabItem>
<TabItem value="response" label="Response 201">

Body (JSON):
```json
{
  "id": "UUID",
  "compra_id": "UUID",
  "fecha_emision": "2026-02-24",
  "estado": "ENCOLADA",
  "estado_sri": "PENDIENTE",
  "sri_intentos": 0,
  "sri_ultimo_error": null,
  "total_retenido": "0.90",
  "detalles": [
    {
      "id": "UUID",
      "codigo_retencion_sri": "332",
      "tipo": "IVA",
      "porcentaje": "30.00",
      "base_calculo": "3.00",
      "valor_retenido": "0.90"
    }
  ]
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| base_calculo | decimal | Enviado por cliente | El backend calcula valor_retenido por detalle. |
| total_retenido | decimal | Suma de detalles | Se calcula y se guarda en retencion. |
| estado | string | ENCOLADA | Este endpoint siempre encola a SRI. |
| duplicidad | regla | Si hay retencion activa, error 400 | Una retencion activa por compra. |

---

POST /api/v1/retenciones/\{retencion_id\}/emitir
Proposito: Emite una retencion ya creada. Actualiza la CxP asociada sumando el valor retenido y cambia estado a EMITIDA o ENCOLADA segun encolar.

<Tabs>
<TabItem value="request" label="Request">

Path params:
- retencion_id (UUID)

Body (JSON):
```json
{
  "usuario_auditoria": "user@dominio.com",
  "encolar": false
}
```

</TabItem>
<TabItem value="response" label="Response 200">

Body (JSON):
```json
{
  "id": "UUID",
  "compra_id": "UUID",
  "fecha_emision": "2026-02-24",
  "estado": "EMITIDA",
  "estado_sri": "PENDIENTE",
  "sri_intentos": 0,
  "sri_ultimo_error": null,
  "total_retenido": "0.90",
  "detalles": [
    {
      "id": "UUID",
      "codigo_retencion_sri": "332",
      "tipo": "IVA",
      "porcentaje": "30.00",
      "base_calculo": "3.00",
      "valor_retenido": "0.90"
    }
  ]
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| encolar | boolean | Si true, se encola FE | Cambia estado a ENCOLADA y encola documento en orquestador asincrono SRI. |
| cxp | interno | Se bloquea y actualiza | Suma valor_retenido y recalcula saldo. |
| estado | string | EMITIDA o ENCOLADA | Segun el flag encolar. |

---

## Comportamientos idempotentes y asincronia FE

- `POST /api/v1/compras/{compra_id}/anular`: si la compra ya esta `ANULADA`, el backend retorna la compra sin reprocesar.
- `POST /api/v1/retenciones/{retencion_id}/emitir`: si la retencion ya esta `EMITIDA` o `ENCOLADA`, retorna estado actual sin aplicar doble impacto en CxP.
- Cuando una retencion queda `ENCOLADA`, el estado final SRI (`AUTORIZADO`, `RECHAZADO`, etc.) se actualiza por procesamiento asincrono del orquestador FE.

---

GET /api/v1/retenciones/\{retencion_id\}/fe-payload
Proposito: Devuelve el payload FE-EC de la retencion para integracion con facturacion electronica.

<Tabs>
<TabItem value="request" label="Request">

Path params:
- retencion_id (UUID)

</TabItem>
<TabItem value="response" label="Response 200">

Body (JSON):
```json
{
  "infoTributaria": {},
  "infoCompRetencion": {},
  "impuestos": []
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| payload | object | FE-EC | Mapa libre con estructura FE generada por FEMapperService. |

---

GET /api/v1/cxp
Proposito: Lista cuentas por pagar para bandeja administrativa de compras/tesorería.

<Tabs>
<TabItem value="request-cxp-list" label="Request">

Query params:

- `limit` (int, default `50`, min `1`, max `500`)
- `offset` (int, default `0`, min `0`)
- `only_active` (bool, default `true`)
- `estado` (`PENDIENTE|PARCIAL|PAGADA|ANULADA`) opcional
- `texto` (string) opcional; busca por identificación proveedor o secuencial factura

</TabItem>
<TabItem value="response-cxp-list" label="Response 200">

Body (JSON):
```json
{
  "items": [
    {
      "id": "UUID",
      "compra_id": "UUID",
      "proveedor_id": "UUID",
      "proveedor": "1790012345001",
      "numero_factura": "001-001-123456789",
      "fecha_emision": "2026-02-26",
      "valor_total_factura": "100.00",
      "valor_retenido": "10.00",
      "pagos_acumulados": "40.00",
      "saldo_pendiente": "50.00",
      "estado": "PARCIAL"
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

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| estado | enum | filtro opcional | Filtra por estado de CxP. |
| texto | string | filtro opcional | Busca por identificación proveedor o secuencial factura. |
| items[].saldo_pendiente | decimal | calculado | `valor_total_factura - valor_retenido - pagos_acumulados`. |

---

GET /api/v1/cxp/\{compra_id\}
Proposito: Obtiene la cuenta por pagar asociada a una compra específica.

<Tabs>
<TabItem value="request-cxp-detail" label="Request">

Path params:

- `compra_id` (UUID)

</TabItem>
<TabItem value="response-cxp-detail" label="Response 200">

Body (JSON):
```json
{
  "id": "UUID",
  "compra_id": "UUID",
  "valor_total_factura": "100.00",
  "valor_retenido": "10.00",
  "pagos_acumulados": "40.00",
  "saldo_pendiente": "50.00",
  "estado": "PARCIAL",
  "creado_en": "2026-02-26T10:00:00",
  "actualizado_en": "2026-02-26T10:15:00"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| compra_id | UUID | requerido | Compra asociada a la cuenta por pagar. |
| estado | enum | derivado de saldos | `PENDIENTE`, `PARCIAL`, `PAGADA` o `ANULADA`. |

---

POST /api/v1/cxp/\{compra_id\}/pagos
Proposito: Registra un pago de proveedor sobre la CxP de la compra y recalcula saldo/estado.

<Tabs>
<TabItem value="request-cxp-pay" label="Request">

Path params:

- `compra_id` (UUID)

Body (JSON):
```json
{
  "monto": "40.00",
  "fecha": "2026-02-26",
  "forma_pago": "EFECTIVO",
  "usuario_auditoria": "tesoreria@empresa.com"
}
```

</TabItem>
<TabItem value="response-cxp-pay" label="Response 201">

Body (JSON):
```json
{
  "id": "UUID",
  "cuenta_por_pagar_id": "UUID",
  "monto": "40.00",
  "fecha": "2026-02-26",
  "forma_pago": "EFECTIVO"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Regla / Origen | Descripcion |
|---|---|---|---|
| monto | decimal | `> 0` y `<= saldo_pendiente` | Si excede saldo, retorna `400`. |
| forma_pago | enum | catálogo SRI | `EFECTIVO`, `TARJETA`, `TRANSFERENCIA`. |
| bloqueo | interno | `with_for_update` | Evita carreras y sobrepagos concurrentes. |
| recalculo | interno | automático | Ajusta `pagos_acumulados`, `saldo_pendiente` y estado (`PARCIAL`/`PAGADA`). |
