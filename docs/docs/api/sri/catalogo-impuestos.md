---
id: catalogo-impuestos
title: "SRI: Catálogo de Impuestos"
sidebar_position: 3
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# SRI: Catálogo de Impuestos

Este apartado documenta `src/osiris/modules/sri/impuesto_catalogo` (`/api/v1/impuestos`).

## Objetivo funcional

Administrar catálogo tributario mínimo para IVA/ICE/IRBPNR, con vigencias y reglas de consistencia por tipo de impuesto.

## Enums del catálogo

| Campo | Valores |
|---|---|
| `tipo_impuesto` | `IVA`, `ICE`, `IRBPNR` |
| `clasificacion_iva` | `GRAVADO`, `EXENTO`, `NO_OBJETO`, `DIFERENCIADO`, `OTRO` |
| `modo_calculo_ice` | `AD_VALOREM`, `ESPECIFICO`, `MIXTO` |
| `unidad_base` | `UNIDAD`, `LITRO`, `KILO`, `MIL_UNIDADES`, `OTRO` |
| `aplica_a` | `BIEN`, `SERVICIO`, `AMBOS` |

## Validaciones de negocio en creación

1. `codigo_tipo_impuesto` debe corresponder al tipo:
   - IVA -> `"2"`
   - ICE -> `"3"`
   - IRBPNR -> `"5"`
2. Reglas por tipo:
   - IVA: requiere `porcentaje_iva` + `clasificacion_iva`
   - ICE: requiere al menos una tarifa (`tarifa_ad_valorem` o `tarifa_especifica`) + `modo_calculo_ice` + `unidad_base`
   - IRBPNR: requiere `tarifa_especifica` + `unidad_base`
3. Vigencia:
   - `vigente_hasta` no puede ser menor que `vigente_desde`
4. Unicidad:
   - no se permite duplicar combinación `codigo_sri + descripcion`

---

`GET /api/v1/impuestos`

Propósito: listado paginado de impuestos.

Query params:

| Param | Tipo | Descripción |
|---|---|---|
| `limit` | int | default `50`, min `1`, max `100` |
| `offset` | int | default `0` |
| `tipo_impuesto` | enum | filtra por `IVA`, `ICE`, `IRBPNR` |
| `solo_vigentes` | bool | aplicado cuando se usa `tipo_impuesto` |

<Tabs>
<TabItem value="response" label="Response 200">

```json
{
  "items": [
    {
      "id": "b6bb37b3-7f4f-4e59-a266-0016770e0e17",
      "tipo_impuesto": "IVA",
      "codigo_tipo_impuesto": "2",
      "codigo_sri": "4",
      "descripcion": "IVA 15%",
      "vigente_desde": "2024-04-01",
      "vigente_hasta": null,
      "aplica_a": "AMBOS",
      "activo": true,
      "porcentaje_iva": "15.00",
      "clasificacion_iva": "GRAVADO"
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

---

`GET /api/v1/impuestos/activos-vigentes`

Propósito: retorna impuestos activos vigentes a una fecha.

Query params:

| Param | Tipo | Descripción |
|---|---|---|
| `fecha` | date | opcional; si no se envía usa hoy |

---

`GET /api/v1/impuestos/{impuesto_id}`

Propósito: obtener detalle de un impuesto específico.

---

`POST /api/v1/impuestos`

Propósito: crear un impuesto del catálogo.

<Tabs>
<TabItem value="request-iva" label="Request IVA">

```json
{
  "tipo_impuesto": "IVA",
  "codigo_tipo_impuesto": "2",
  "codigo_sri": "4",
  "descripcion": "IVA 15%",
  "vigente_desde": "2024-04-01",
  "vigente_hasta": null,
  "aplica_a": "AMBOS",
  "porcentaje_iva": "15.00",
  "clasificacion_iva": "GRAVADO",
  "usuario_auditoria": "admin@osiris"
}
```

</TabItem>
<TabItem value="request-ice" label="Request ICE">

```json
{
  "tipo_impuesto": "ICE",
  "codigo_tipo_impuesto": "3",
  "codigo_sri": "3051",
  "descripcion": "ICE bebidas alcohólicas",
  "vigente_desde": "2024-01-01",
  "vigente_hasta": null,
  "aplica_a": "BIEN",
  "tarifa_ad_valorem": "75.00",
  "tarifa_especifica": null,
  "modo_calculo_ice": "AD_VALOREM",
  "unidad_base": "UNIDAD",
  "usuario_auditoria": "admin@osiris"
}
```

</TabItem>
<TabItem value="error-409" label="Error 409">

```json
{
  "detail": "Ya existe un impuesto con código SRI '4' y descripción 'IVA 15%'"
}
```

</TabItem>
</Tabs>

---

`PUT /api/v1/impuestos/{impuesto_id}`

Propósito: actualizar un impuesto existente.

Ejemplo:

```json
{
  "descripcion": "IVA 15% bienes y servicios",
  "vigente_hasta": null,
  "usuario_auditoria": "admin@osiris"
}
```

---

`DELETE /api/v1/impuestos/{impuesto_id}`

Propósito: desactivar impuesto (`soft delete`).

- HTTP: `204 No Content`.
- Efecto: `activo=false`.

## Diccionario de campos clave

| Campo | Tipo | Regla |
|---|---|---|
| `codigo_sri` | string | código oficial/referencial SRI |
| `codigo_tipo_impuesto` | string | debe coincidir con `tipo_impuesto` |
| `vigente_desde` | date | inicio de vigencia |
| `vigente_hasta` | date\|null | fin de vigencia opcional |
| `porcentaje_iva` | decimal\|null | obligatorio para IVA |
| `tarifa_ad_valorem` | decimal\|null | opcional ICE |
| `tarifa_especifica` | decimal\|null | obligatorio en IRBPNR |

