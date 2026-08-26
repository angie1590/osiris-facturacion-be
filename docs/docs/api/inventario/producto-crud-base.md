---
id: producto-crud-base
title: "Producto: CRUD Base"
sidebar_position: 5
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Producto: CRUD Base

## Política de Registros Activos (Frontend)

- En listados, usar `only_active=true` por defecto.
- Los inactivos representan borrado lógico y deben usarse solo en pantallas administrativas.
- `DELETE` no elimina físicamente; cambia `activo=false`.

Este documento cubre el CRUD base de `producto` y sus operaciones directas de atributos e impuestos:
- `GET /api/v1/productos`
- `GET /api/v1/productos/{producto_id}`
- `POST /api/v1/productos`
- `PUT /api/v1/productos/{producto_id}`
- `DELETE /api/v1/productos/{producto_id}`
- `PUT /api/v1/productos/{producto_id}/atributos`
- `GET /api/v1/productos/{producto_id}/impuestos`
- `POST /api/v1/productos/{producto_id}/impuestos`
- `DELETE /api/v1/productos/impuestos/{producto_impuesto_id}`

---

## GET `/api/v1/productos`

Listado **liviano** para grillas y búsquedas rápidas. Devuelve metadata base y paginación, sin resolver el detalle completo de relaciones.

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "limit": 50,
  "offset": 0,
  "only_active": true
}
```

  </TabItem>
  <TabItem value="response200" label="Response 200">

```json
{
  "items": [
    {
      "id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
      "nombre": "Laptop Gamer X",
      "tipo": "BIEN",
      "pvp": "2999.00",
      "cantidad": "0.0000"
    }
  ],
  "meta": {
    "total": 1,
    "limit": 50,
    "offset": 0,
    "page": 1,
    "page_count": 1
  }
}
```

  </TabItem>
</Tabs>

### Diccionario de Datos - GET `/api/v1/productos`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `limit` | int | No | min 1, max 1000, default 50 |
| `offset` | int | No | min 0, default 0 |
| `only_active` | bool | No | default true |
| `items[].id` | UUID | Sí | PK |
| `items[].nombre` | string | Sí | max 255, unique |
| `items[].tipo` | enum | Sí | `BIEN` \| `SERVICIO` |
| `items[].pvp` | decimal | Sí | escala monetaria |
| `items[].cantidad` | decimal | Sí | stock agregado del producto |
| `meta.total` | int | Sí | total registros |
| `meta.limit` | int | Sí | tamaño página |
| `meta.offset` | int | Sí | desplazamiento |
| `meta.page` | int | Sí | página calculada |
| `meta.page_count` | int | Sí | total páginas |

---

## GET `/api/v1/productos/{producto_id}`

Obtiene el detalle completo del producto. Este endpoint sí trae composición completa (casa comercial, categorías, proveedores, impuestos, bodegas) y estructura de atributos con herencia por categorías.

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa"
}
```

  </TabItem>
  <TabItem value="response200" label="Response 200">

```json
{
  "id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
  "nombre": "Laptop Gamer X",
  "tipo": "BIEN",
  "pvp": "2999.00",
  "cantidad": "0.0000",
  "permite_fracciones": false,
  "casa_comercial": {
    "nombre": "Casa ACME"
  },
  "categorias": [
    {
      "id": "3d3a9558-ec2f-4a11-95ce-ccf00f9ce2a9",
      "nombre": "Laptops"
    }
  ],
  "proveedores_persona": [],
  "proveedores_sociedad": [],
  "atributos": [
    {
      "atributo": {
        "id": "2a2bf5b8-e95e-4f6b-850d-c3ec4ce7c38f",
        "nombre": "Color",
        "tipo_dato": "string"
      },
      "valor": "Negro",
      "obligatorio": true,
      "orden": 1
    }
  ],
  "impuestos": [
    {
      "nombre": "IVA 15%",
      "codigo": "2",
      "porcentaje": "15.00"
    }
  ],
  "bodegas": [
    {
      "codigo_bodega": "BOD-MATRIZ",
      "nombre_bodega": "Bodega Matriz"
    }
  ]
}
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Producto no encontrado"
}
```

  </TabItem>
</Tabs>

### Diccionario de Datos - GET `/api/v1/productos/{producto_id}`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `id` | UUID | Sí | path param |
| `nombre` | string | Sí | max 255, unique |
| `tipo` | enum | Sí | `BIEN` \| `SERVICIO` |
| `pvp` | decimal | Sí | escala monetaria |
| `cantidad` | decimal | Sí | stock agregado del producto |
| `permite_fracciones` | bool | Sí | define si el producto admite cantidades fraccionarias |
| `casa_comercial` | object/null | No | objeto anidado |
| `categorias` | list | Sí | categorías del producto |
| `proveedores_persona` | list | Sí | proveedores persona |
| `proveedores_sociedad` | list | Sí | proveedores sociedad |
| `atributos` | list | Sí | detalle con herencia por categoría |
| `impuestos` | list | Sí | impuestos aplicados |
| `bodegas` | list | Sí | disponibilidad por bodega |

---

## POST `/api/v1/productos`

Crea un producto nuevo y retorna el contrato completo.

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "nombre": "Laptop Gamer X",
  "descripcion": "Portátil de alto rendimiento",
  "codigo_barras": "1234567890123",
  "tipo": "BIEN",
  "pvp": "2999.00",
  "permite_fracciones": false,
  "casa_comercial_id": "6fc4e4d7-bf58-4eb3-a1db-1977e09e0f8e",
  "categoria_ids": [
    "3d3a9558-ec2f-4a11-95ce-ccf00f9ce2a9"
  ],
  "impuesto_catalogo_ids": [
    "bb8ad8d6-ecf3-4f3d-9f0d-b5a6d4d3f2c1"
  ],
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response201" label="Response 201">

```json
{
  "id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
  "nombre": "Laptop Gamer X",
  "tipo": "BIEN",
  "pvp": "2999.00",
  "cantidad": "0.0000",
  "permite_fracciones": false,
  "casa_comercial": {
    "nombre": "Casa ACME"
  },
  "categorias": [],
  "proveedores_persona": [],
  "proveedores_sociedad": [],
  "atributos": [],
  "impuestos": [],
  "bodegas": []
}
```

  </TabItem>
  <TabItem value="response400" label="Response 400">

```json
{
  "detail": "El PVP debe ser mayor que cero"
}
```

```json
{
  "detail": "Solo se permiten categorías hoja (sin hijos) para el producto."
}
```

```json
{
  "detail": "Debe incluir exactamente un impuesto de tipo IVA. Los productos siempre deben tener IVA."
}
```

  </TabItem>
</Tabs>

### Diccionario de Datos - POST `/api/v1/productos`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `nombre` | string | Sí | max 255, unique |
| `descripcion` | string/null | No | max 1000 |
| `codigo_barras` | string/null | No | max 100 |
| `tipo` | enum | No | default `BIEN`; `BIEN` \| `SERVICIO` |
| `pvp` | decimal | Sí | **debe ser > 0**, redondeado a 2 decimales |
| `permite_fracciones` | bool | No | default `false` |
| `casa_comercial_id` | UUID/null | No | FK válida y activa |
| `categoria_ids` | UUID[]/null | No | si se envía, categorías hoja |
| `impuesto_catalogo_ids` | UUID[] | Sí | obligatorio; impuestos activos; IVA obligatorio; sin duplicar tipo de impuesto |
| `usuario_auditoria` | string/null | No | auditoría |

### Validaciones de negocio (POST)

- `tipo`: solo valores del enum `TipoProducto`.
- `pvp`: validación positiva y normalización a 2 decimales.
- `casa_comercial_id`: validación FK por servicio base.
- `categoria_ids`: solo categorías hoja (sin hijos).
- `impuesto_catalogo_ids`: al menos un IVA, impuestos existentes/activos, y sin repetir tipo de impuesto.

---

## PUT `/api/v1/productos/{producto_id}`

Actualiza parcialmente un producto y retorna el contrato completo.

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "nombre": "Laptop Gamer X Pro",
  "tipo": "BIEN",
  "pvp": "3199.90",
  "permite_fracciones": false,
  "casa_comercial_id": "6fc4e4d7-bf58-4eb3-a1db-1977e09e0f8e",
  "categoria_ids": [
    "3d3a9558-ec2f-4a11-95ce-ccf00f9ce2a9"
  ],
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response200" label="Response 200">

```json
{
  "id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
  "nombre": "Laptop Gamer X Pro",
  "tipo": "BIEN",
  "pvp": "3199.90",
  "cantidad": "0.0000",
  "permite_fracciones": false,
  "casa_comercial": {
    "nombre": "Casa ACME"
  },
  "categorias": [],
  "proveedores_persona": [],
  "proveedores_sociedad": [],
  "atributos": [],
  "impuestos": [],
  "bodegas": []
}
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Producto 9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa no encontrado"
}
```

  </TabItem>
</Tabs>

### Diccionario de Datos - PUT `/api/v1/productos/{producto_id}`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `id` | UUID | Sí | path param |
| `nombre` | string/null | No | max 255, unique |
| `descripcion` | string/null | No | max 1000 |
| `codigo_barras` | string/null | No | max 100 |
| `tipo` | enum/null | No | `BIEN` \| `SERVICIO` |
| `pvp` | decimal/null | No | si se envía, **debe ser > 0**, redondeo 2 decimales |
| `permite_fracciones` | bool/null | No | define si el producto permite fracciones |
| `casa_comercial_id` | UUID/null | No | FK válida y activa |
| `categoria_ids` | UUID[]/null | No | si se envía, categorías hoja |
| `usuario_auditoria` | string/null | No | auditoría |

### Validaciones de negocio (PUT)

- `tipo`: enum `TipoProducto`.
- `pvp`: si se envía, debe ser mayor que cero.
- `casa_comercial_id`: validación FK por servicio base.
- `categoria_ids`: si se envían, deben ser categorías hoja.

---

## DELETE `/api/v1/productos/{producto_id}`

Eliminación lógica del producto (`activo=false`).

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa"
}
```

  </TabItem>
  <TabItem value="response204" label="Response 204">

```json
null
```

  </TabItem>
</Tabs>

### Diccionario de Datos - DELETE `/api/v1/productos/{producto_id}`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `id` | UUID | Sí | path param |
| `status_code` | int | Sí | 204 sin cuerpo |
| `activo` | bool | Sí | soft delete |

---

## Reglas Operativas de Stock y Fracciones

1. `cantidad` del producto es un acumulado decimal sincronizado desde stock materializado.
2. Si `permite_fracciones=false`, el frontend debe forzar cantidades enteras en operaciones de inventario.
3. Si el producto es de tipo `SERVICIO`, no debe permitirse stock positivo en asignaciones por bodega.
4. Para cálculos y renderizado, tratar `pvp` y `cantidad` como decimales exactos (no `float`).

---

## PUT `/api/v1/productos/{producto_id}/atributos`

Actualiza/crea en bloque los valores de atributos del producto.  
Valida aplicabilidad del atributo según categorías actuales y tipo de dato esperado.

<Tabs>
  <TabItem value="request" label="Request" default>

```json
[
  {
    "atributo_id": "2a2bf5b8-e95e-4f6b-850d-c3ec4ce7c38f",
    "valor": "Negro"
  },
  {
    "atributo_id": "2a2bf5b8-e95e-4f6b-850d-c3ec4ce7c38e",
    "valor": 15
  }
]
```

  </TabItem>
  <TabItem value="response200" label="Response 200">

```json
[
  {
    "id": "3f1f5ed1-705f-4d5e-a576-01a4ab9a8001",
    "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
    "atributo_id": "2a2bf5b8-e95e-4f6b-850d-c3ec4ce7c38f",
    "valor": "Negro",
    "activo": true
  }
]
```

  </TabItem>
  <TabItem value="response400" label="Response 400">

```json
{
  "detail": "El atributo Color (2a2bf5b8-e95e-4f6b-850d-c3ec4ce7c38f) no aplica a las categorias actuales del producto."
}
```

```json
{
  "detail": "Valor incompatible para el atributo Peso. Se esperaba un tipo decimal."
}
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Producto 9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa no encontrado"
}
```

  </TabItem>
</Tabs>

### Diccionario de Datos - PUT `/api/v1/productos/{producto_id}/atributos`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `producto_id` | UUID | Sí | path param |
| `[].atributo_id` | UUID | Sí | debe existir y estar activo |
| `[].valor` | any | Sí | se valida por tipo del atributo (`string`, `integer`, `decimal`, `boolean`, `date`) |

### Notas funcionales

- No elimina atributos no enviados; solo hace upsert de los incluidos.
- Si un atributo no pertenece a la jerarquía de categorías del producto, la API rechaza toda la operación.

---

## GET `/api/v1/productos/{producto_id}/impuestos`

Lista el detalle de impuestos del catálogo SRI asignados al producto.

<Tabs>
  <TabItem value="response200" label="Response 200" default>

```json
[
  {
    "id": "41b846bf-6c0a-42a1-9f38-b47e0c937f61",
    "codigo_sri": "2",
    "descripcion": "IVA 15%",
    "tipo_impuesto": "IVA",
    "porcentaje_iva": "15.00",
    "activo": true
  }
]
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Producto no encontrado o inactivo"
}
```

  </TabItem>
</Tabs>

### Diccionario de Datos - GET `/api/v1/productos/{producto_id}/impuestos`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `producto_id` | UUID | Sí | path param |
| `[].codigo_sri` | string | Sí | código SRI del impuesto |
| `[].tipo_impuesto` | enum | Sí | `IVA`, `ICE`, `IRBPNR` (según catálogo) |
| `[].activo` | bool | Sí | solo impuestos activos |

---

## POST `/api/v1/productos/{producto_id}/impuestos`

Asigna un impuesto a un producto con validación tributaria y de compatibilidad por tipo (`BIEN`/`SERVICIO`).

> Nota importante para frontend: en la implementación actual estos datos llegan como **query params**, no como body JSON.

<Tabs>
  <TabItem value="request" label="Request (Query Params)" default>

```json
{
  "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
  "impuesto_catalogo_id": "41b846bf-6c0a-42a1-9f38-b47e0c937f61",
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response201" label="Response 201">

```json
{
  "id": "912fa1e3-f7f1-4a2d-bab3-73b4caa263e8",
  "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
  "impuesto_catalogo_id": "41b846bf-6c0a-42a1-9f38-b47e0c937f61",
  "codigo_impuesto_sri": "2",
  "codigo_porcentaje_sri": "4",
  "tarifa": "15.00",
  "activo": true,
  "impuesto": {
    "id": "41b846bf-6c0a-42a1-9f38-b47e0c937f61",
    "codigo_sri": "2",
    "descripcion": "IVA 15%",
    "tipo_impuesto": "IVA"
  }
}
```

  </TabItem>
  <TabItem value="response400" label="Response 400">

```json
{
  "detail": "El impuesto '2' no está vigente actualmente"
}
```

```json
{
  "detail": "Este impuesto no aplica para productos de tipo SERVICIO"
}
```

```json
{
  "detail": "La asignación ya existe para este producto e impuesto."
}
```

  </TabItem>
</Tabs>

### Diccionario de Datos - POST `/api/v1/productos/{producto_id}/impuestos`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `producto_id` | UUID | Sí | path param |
| `impuesto_catalogo_id` | UUID | Sí | query param |
| `usuario_auditoria` | string | Sí | query param |
| `tarifa` | decimal | Sí | resuelta desde catálogo SRI (IVA/ICE) |

### Notas funcionales

- Si ya existía un impuesto del mismo tipo (ej. IVA), se inactiva y se reemplaza por el nuevo.
- Aplica validación de vigencia (`fecha_inicio`/`fecha_fin`) del impuesto en catálogo SRI.

---

## DELETE `/api/v1/productos/impuestos/{producto_impuesto_id}`

Realiza soft delete de una asignación producto-impuesto.

<Tabs>
  <TabItem value="response204" label="Response 204" default>

```json
null
```

  </TabItem>
  <TabItem value="response400" label="Response 400">

```json
{
  "detail": "No se puede eliminar el impuesto IVA. El IVA es obligatorio para todos los productos (requerimiento SRI). Para cambiar el IVA, asigne un nuevo IVA que reemplazará automáticamente el anterior."
}
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Asignación de impuesto no encontrada"
}
```

  </TabItem>
</Tabs>

### Diccionario de Datos - DELETE `/api/v1/productos/impuestos/{producto_impuesto_id}`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `producto_impuesto_id` | UUID | Sí | path param |
| `status_code` | int | Sí | 204 sin cuerpo |
| `activo` | bool | Sí | se marca en false (soft delete) |
