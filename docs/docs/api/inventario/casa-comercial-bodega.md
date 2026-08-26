---
id: casa-comercial-bodega
title: "Casa Comercial y Bodega"
sidebar_position: 4
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Casa Comercial y Bodega

## Política de Registros Activos (Frontend)

- En listados, usar por defecto filtros de activos cuando existan (`only_active=true`).
- Registros inactivos representan borrado lógico y no deben mostrarse en flujos operativos normales.
- Para administración/auditoría, el frontend puede consultar inactivos explícitamente.

## Casa Comercial

### GET `/api/v1/casas-comerciales`

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
      "id": "d0bdb05e-5f7a-40b5-b6db-9f10f9efe7a4",
      "nombre": "Casa ACME",
      "activo": true,
      "creado_en": "2026-02-24T10:00:00",
      "actualizado_en": "2026-02-24T10:00:00",
      "usuario_auditoria": "api"
    }
  ],
  "meta": {
    "total": 1,
    "limit": 50,
    "offset": 0
  }
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - GET `/api/v1/casas-comerciales`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `limit` | int | No | min 1, max 1000, default 50 |
| `offset` | int | No | min 0, default 0 |
| `only_active` | bool | No | default true |
| `items[].id` | UUID | Sí | PK |
| `items[].nombre` | string | Sí | unique, max 120 |
| `items[].activo` | bool | Sí | soft delete |
| `items[].creado_en` | datetime | Sí | auditoría |
| `items[].actualizado_en` | datetime | Sí | auditoría |
| `items[].usuario_auditoria` | string/null | No | auditoría |
| `meta.total` | int | Sí | total de registros |
| `meta.limit` | int | Sí | tamaño de página |
| `meta.offset` | int | Sí | desplazamiento |

### GET `/api/v1/casas-comerciales/{item_id}`

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "item_id": "d0bdb05e-5f7a-40b5-b6db-9f10f9efe7a4"
}
```

  </TabItem>
  <TabItem value="response200" label="Response 200">

```json
{
  "id": "d0bdb05e-5f7a-40b5-b6db-9f10f9efe7a4",
  "nombre": "Casa ACME",
  "activo": true,
  "creado_en": "2026-02-24T10:00:00",
  "actualizado_en": "2026-02-24T10:00:00",
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Casa-comercial d0bdb05e-5f7a-40b5-b6db-9f10f9efe7a4 not found"
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - GET `/api/v1/casas-comerciales/{item_id}`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `item_id` | UUID | Sí | path param |
| `id` | UUID | Sí | PK |
| `nombre` | string | Sí | unique, max 120 |
| `activo` | bool | Sí | soft delete |
| `creado_en` | datetime | Sí | auditoría |
| `actualizado_en` | datetime | Sí | auditoría |
| `usuario_auditoria` | string/null | No | auditoría |

### POST `/api/v1/casas-comerciales`

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "nombre": "Casa ACME",
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response201" label="Response 201">

```json
{
  "id": "d0bdb05e-5f7a-40b5-b6db-9f10f9efe7a4",
  "nombre": "Casa ACME",
  "activo": true,
  "creado_en": "2026-02-24T10:00:00",
  "actualizado_en": "2026-02-24T10:00:00",
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response409" label="Response 409">

```json
{
  "detail": "Registro duplicado: el valor de 'nombre' ya existe."
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - POST `/api/v1/casas-comerciales`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `nombre` | string | Sí | unique, max 120 |
| `usuario_auditoria` | string/null | No | auditoría |
| `id` | UUID | Sí | generado por sistema |
| `activo` | bool | Sí | default true |

### PUT `/api/v1/casas-comerciales/{item_id}`

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "item_id": "d0bdb05e-5f7a-40b5-b6db-9f10f9efe7a4",
  "body": {
    "nombre": "Casa ACME Actualizada",
    "usuario_auditoria": "api"
  }
}
```

  </TabItem>
  <TabItem value="response200" label="Response 200">

```json
{
  "id": "d0bdb05e-5f7a-40b5-b6db-9f10f9efe7a4",
  "nombre": "Casa ACME Actualizada",
  "activo": true,
  "creado_en": "2026-02-24T10:00:00",
  "actualizado_en": "2026-02-24T10:10:00",
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Casa-comercial d0bdb05e-5f7a-40b5-b6db-9f10f9efe7a4 not found"
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - PUT `/api/v1/casas-comerciales/{item_id}`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `item_id` | UUID | Sí | path param |
| `nombre` | string/null | No | unique, max 120 |
| `usuario_auditoria` | string/null | No | update parcial |
| `actualizado_en` | datetime | Sí | auditoría |

### DELETE `/api/v1/casas-comerciales/{item_id}`

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "item_id": "d0bdb05e-5f7a-40b5-b6db-9f10f9efe7a4"
}
```

  </TabItem>
  <TabItem value="response204" label="Response 204">

```json
null
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Casa-comercial d0bdb05e-5f7a-40b5-b6db-9f10f9efe7a4 not found"
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - DELETE `/api/v1/casas-comerciales/{item_id}`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `item_id` | UUID | Sí | path param |
| `status_code` | int | Sí | 204 sin cuerpo |
| `activo` | bool | Sí | pasa a false (soft delete) |

## Bodega

### GET `/api/v1/bodegas`

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "skip": 0,
  "limit": 50,
  "empresa_id": "9f0de3b2-3b84-4f2f-9adf-c12b41f0a312",
  "sucursal_id": null
}
```

  </TabItem>
  <TabItem value="response" label="Response 200">

```json
[
  {
    "id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
    "codigo_bodega": "BOD-MATRIZ",
    "nombre_bodega": "Bodega Matriz",
    "descripcion": "Bodega principal",
    "empresa_id": "9f0de3b2-3b84-4f2f-9adf-c12b41f0a312",
    "sucursal_id": null,
    "usuario_auditoria": "api",
    "activo": true,
    "creado_en": "2026-02-24T10:00:00",
    "actualizado_en": "2026-02-24T10:00:00"
  }
]
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - GET `/api/v1/bodegas`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `skip` | int | No | min 0, default 0 |
| `limit` | int | No | min 1, max 200, default 50 |
| `empresa_id` | UUID/null | No | filtro opcional |
| `sucursal_id` | UUID/null | No | filtro opcional |
| `[].id` | UUID | Sí | PK |
| `[].codigo_bodega` | string | Sí | max 20 |
| `[].nombre_bodega` | string | Sí | max 100 |
| `[].descripcion` | string/null | No | max 255 |
| `[].empresa_id` | UUID | Sí | FK tbl_empresa |
| `[].sucursal_id` | UUID/null | No | FK tbl_sucursal |
| `[].activo` | bool | Sí | listado retorna activos |
| `[].creado_en` | datetime | Sí | auditoría |
| `[].actualizado_en` | datetime | Sí | auditoría |
| `[].usuario_auditoria` | string/null | No | auditoría |

### GET `/api/v1/bodegas/{id}`

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6"
}
```

  </TabItem>
  <TabItem value="response" label="Response 200">

```json
{
  "id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
  "codigo_bodega": "BOD-MATRIZ",
  "nombre_bodega": "Bodega Matriz",
  "descripcion": "Bodega principal",
  "empresa_id": "9f0de3b2-3b84-4f2f-9adf-c12b41f0a312",
  "sucursal_id": null,
  "usuario_auditoria": "api",
  "activo": true,
  "creado_en": "2026-02-24T10:00:00",
  "actualizado_en": "2026-02-24T10:00:00"
}
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Bodega no encontrada"
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - GET `/api/v1/bodegas/{id}`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `id` | UUID | Sí | path param |
| `codigo_bodega` | string | Sí | max 20 |
| `nombre_bodega` | string | Sí | max 100 |
| `descripcion` | string/null | No | max 255 |
| `empresa_id` | UUID | Sí | FK tbl_empresa |
| `sucursal_id` | UUID/null | No | FK tbl_sucursal |
| `activo` | bool | Sí | soft delete |
| `creado_en` | datetime | Sí | auditoría |
| `actualizado_en` | datetime | Sí | auditoría |
| `usuario_auditoria` | string/null | No | auditoría |

### POST `/api/v1/bodegas`

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "codigo_bodega": "BOD-MATRIZ",
  "nombre_bodega": "Bodega Matriz",
  "descripcion": "Bodega principal",
  "empresa_id": "9f0de3b2-3b84-4f2f-9adf-c12b41f0a312",
  "sucursal_id": null,
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response201" label="Response 201">

```json
{
  "id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
  "codigo_bodega": "BOD-MATRIZ",
  "nombre_bodega": "Bodega Matriz",
  "descripcion": "Bodega principal",
  "empresa_id": "9f0de3b2-3b84-4f2f-9adf-c12b41f0a312",
  "sucursal_id": null,
  "usuario_auditoria": "api",
  "activo": true,
  "creado_en": "2026-02-24T10:00:00",
  "actualizado_en": "2026-02-24T10:00:00"
}
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Empresa no encontrada"
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - POST `/api/v1/bodegas`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `codigo_bodega` | string | Sí | max 20 |
| `nombre_bodega` | string | Sí | max 100 |
| `descripcion` | string/null | No | max 255 |
| `empresa_id` | UUID | Sí | FK obligatoria |
| `sucursal_id` | UUID/null | No | FK opcional |
| `usuario_auditoria` | string/null | No | el router usa "api" en servicio |
| `id` | UUID | Sí | generado por sistema |
| `activo` | bool | Sí | default true |

### PUT `/api/v1/bodegas/{id}`

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
  "body": {
    "nombre_bodega": "Bodega Matriz Actualizada",
    "descripcion": "Bodega principal actualizada",
    "usuario_auditoria": "api"
  }
}
```

  </TabItem>
  <TabItem value="response200" label="Response 200">

```json
{
  "id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
  "codigo_bodega": "BOD-MATRIZ",
  "nombre_bodega": "Bodega Matriz Actualizada",
  "descripcion": "Bodega principal actualizada",
  "empresa_id": "9f0de3b2-3b84-4f2f-9adf-c12b41f0a312",
  "sucursal_id": null,
  "usuario_auditoria": "api",
  "activo": true,
  "creado_en": "2026-02-24T10:00:00",
  "actualizado_en": "2026-02-24T10:10:00"
}
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Bodega no encontrada"
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - PUT `/api/v1/bodegas/{id}`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `id` | UUID | Sí | path param |
| `codigo_bodega` | string/null | No | max 20 |
| `nombre_bodega` | string/null | No | max 100 |
| `descripcion` | string/null | No | max 255 |
| `sucursal_id` | UUID/null | No | FK opcional |
| `usuario_auditoria` | string/null | No | update parcial |
| `actualizado_en` | datetime | Sí | auditoría |

### DELETE `/api/v1/bodegas/{id}`

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6"
}
```

  </TabItem>
  <TabItem value="response204" label="Response 204">

```json
null
```

  </TabItem>
  <TabItem value="response404" label="Response 404">

```json
{
  "detail": "Bodega no encontrada"
}
```

  </TabItem>
  <TabItem value="response400" label="Response 400">

```json
{
  "detail": "No se puede eliminar la bodega porque tiene productos asignados."
}
```

```json
{
  "detail": "No se puede eliminar la bodega porque tiene stock disponible."
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - DELETE `/api/v1/bodegas/{id}`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `id` | UUID | Sí | path param |
| `status_code` | int | Sí | 204 sin cuerpo |
| `activo` | bool | Sí | pasa a false (soft delete) si no tiene productos/stock |

---

## Movimientos de Inventario (Kárdex Operativo)

Los movimientos de inventario son el origen del kárdex y de la tabla materializada de stock.  
Flujo recomendado para frontend:

1. Crear movimiento en `BORRADOR`.
2. Confirmar movimiento.
3. Consultar kárdex y valoración.

### POST `/api/v1/inventarios/movimientos`

Crea un movimiento en estado `BORRADOR`.  
No altera stock ni costo promedio hasta confirmar.

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "fecha": "2026-02-24",
  "bodega_id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
  "tipo_movimiento": "INGRESO",
  "referencia_documento": "COMPRA-0001",
  "motivo_ajuste": null,
  "usuario_auditoria": "api",
  "detalles": [
    {
      "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
      "cantidad": "10.0000",
      "costo_unitario": "25.0000"
    }
  ]
}
```

  </TabItem>
  <TabItem value="response201" label="Response 201">

```json
{
  "id": "f1bb4a07-f9e8-4ef1-93bb-c5b398013df1",
  "fecha": "2026-02-24",
  "bodega_id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
  "tipo_movimiento": "INGRESO",
  "estado": "BORRADOR",
  "referencia_documento": "COMPRA-0001",
  "motivo_ajuste": null,
  "detalles": [
    {
      "id": "3f1f5ed1-705f-4d5e-a576-01a4ab9a8001",
      "movimiento_inventario_id": "f1bb4a07-f9e8-4ef1-93bb-c5b398013df1",
      "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
      "cantidad": "10.0000",
      "costo_unitario": "25.0000"
    }
  ]
}
```

  </TabItem>
  <TabItem value="response400" label="Response 400">

```json
{
  "detail": [
    {
      "type": "greater_than",
      "loc": ["body", "detalles", 0, "cantidad"],
      "msg": "Input should be greater than 0"
    }
  ]
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - POST `/api/v1/inventarios/movimientos`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `fecha` | date | No | default hoy |
| `bodega_id` | UUID | Sí | FK tbl_bodega |
| `tipo_movimiento` | enum | Sí | `INGRESO`, `EGRESO`, `TRANSFERENCIA`, `AJUSTE` |
| `referencia_documento` | string/null | No | max 120 |
| `motivo_ajuste` | string/null | No | obligatorio al confirmar si tipo es `AJUSTE` |
| `detalles` | list | Sí | mínimo 1 |
| `detalles[].producto_id` | UUID | Sí | FK tbl_producto |
| `detalles[].cantidad` | decimal | Sí | `> 0` |
| `detalles[].costo_unitario` | decimal | Sí | `>= 0` |

### POST `/api/v1/inventarios/movimientos/{movimiento_id}/confirmar`

Confirma un movimiento `BORRADOR` y aplica reglas NIIF/SRI:

- Lock pesimista en stock.
- Regla anti-negativos para egresos/transferencias.
- Recalculo de costo promedio ponderado para ingresos.
- Congelamiento de costo en egresos.
- Validaciones de integridad entre stock, kárdex y cantidad agregada del producto.

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "motivo_ajuste": "Toma física inicial",
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response200" label="Response 200">

```json
{
  "id": "f1bb4a07-f9e8-4ef1-93bb-c5b398013df1",
  "estado": "CONFIRMADO",
  "tipo_movimiento": "INGRESO",
  "detalles": [
    {
      "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
      "cantidad": "10.0000",
      "costo_unitario": "25.0000"
    }
  ]
}
```

  </TabItem>
  <TabItem value="response400" label="Response 400">

```json
{
  "detail": "Solo se puede confirmar movimientos en BORRADOR"
}
```

```json
{
  "detail": "motivo_ajuste es obligatorio para confirmar movimientos de tipo AJUSTE."
}
```

```json
{
  "detail": "Inventario insuficiente: no se permite stock negativo."
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - POST `/api/v1/inventarios/movimientos/{movimiento_id}/confirmar`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `movimiento_id` | UUID | Sí | path param |
| `motivo_ajuste` | string/null | No | obligatorio para `AJUSTE` |
| `usuario_auditoria` | string/null | No | usuario autorizador |
| `estado` | enum | Sí | pasa de `BORRADOR` a `CONFIRMADO` |

### GET `/api/v1/inventarios/kardex`

Consulta cronológica del kárdex operativo por producto + bodega.

<Tabs>
  <TabItem value="request" label="Request" default>

```json
{
  "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
  "bodega_id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
  "fecha_inicio": "2026-02-01",
  "fecha_fin": "2026-02-29"
}
```

  </TabItem>
  <TabItem value="response200" label="Response 200">

```json
{
  "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
  "bodega_id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
  "fecha_inicio": "2026-02-01",
  "fecha_fin": "2026-02-29",
  "saldo_inicial": "0.0000",
  "movimientos": [
    {
      "fecha": "2026-02-24",
      "movimiento_id": "f1bb4a07-f9e8-4ef1-93bb-c5b398013df1",
      "tipo_movimiento": "INGRESO",
      "referencia_documento": "COMPRA-0001",
      "cantidad_entrada": "10.0000",
      "cantidad_salida": "0.0000",
      "saldo_cantidad": "10.0000",
      "costo_unitario_aplicado": "25.0000",
      "valor_movimiento": "250.0000"
    }
  ]
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - GET `/api/v1/inventarios/kardex`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `producto_id` | UUID | Sí | query param |
| `bodega_id` | UUID | Sí | query param |
| `fecha_inicio` | date/null | No | filtro opcional |
| `fecha_fin` | date/null | No | filtro opcional |
| `saldo_inicial` | decimal | Sí | saldo previo al rango |
| `movimientos[]` | list | Sí | solo movimientos `CONFIRMADO` |

### GET `/api/v1/inventarios/valoracion`

Devuelve valoración del inventario por bodega y total global.

<Tabs>
  <TabItem value="response200" label="Response 200" default>

```json
{
  "bodegas": [
    {
      "bodega_id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
      "total_bodega": "250.0000",
      "productos": [
        {
          "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
          "cantidad_actual": "10.0000",
          "costo_promedio_vigente": "25.0000",
          "valor_total": "250.0000"
        }
      ]
    }
  ],
  "total_global": "250.0000"
}
```

  </TabItem>
</Tabs>

#### Diccionario de Datos - GET `/api/v1/inventarios/valoracion`

| Campo | Tipo | Requerido | Restricción |
|---|---|---|---|
| `bodegas` | list | Sí | agrupado por bodega |
| `bodegas[].productos` | list | Sí | stock materializado por producto |
| `total_global` | decimal | Sí | suma de todas las bodegas |

### Notas funcionales para frontend

- Una compra registrada crea ingresos en inventario (kárdex + stock).
- Una venta emitida crea egresos en inventario.
- El stock vigente debe leerse desde entidad de producto/stock materializado; el kárdex es trazabilidad histórica.

---

## Operaciones Avanzadas de Bodega

### POST `/api/v1/inventarios/transferencias`

Realiza una transferencia atómica entre bodegas:

1. Egreso en bodega origen.
2. Ingreso en bodega destino.
3. Si cualquier paso falla, la transacción completa se revierte.

```json
{
  "fecha": "2026-02-24",
  "bodega_origen_id": "3e044677-f970-48f4-830d-3d325111ab01",
  "bodega_destino_id": "3c697f69-a2dc-46c2-a5fd-74e7862f0fd1",
  "referencia_documento": "TRF-001",
  "usuario_auditoria": "api",
  "detalles": [
    {
      "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
      "cantidad": "10.0000"
    }
  ]
}
```

Errores comunes:

- `400`: bodega origen y destino iguales.
- `409`: alguna bodega está inactiva.
- `400`: stock insuficiente al egreso.

### POST `/api/v1/inventarios/movimientos/{movimiento_id}/anular`

Anula un movimiento de inventario:

- Si está en `BORRADOR`, pasa a `ANULADO`.
- Si está en `CONFIRMADO`, el sistema ejecuta reverso automático de stock y luego marca `ANULADO`.

```json
{
  "motivo": "Error de digitación",
  "usuario_auditoria": "api"
}
```

Errores comunes:

- `400`: estado no anulable.
- `404`: movimiento inexistente.

### Criterio MVP para anulaciones (sin módulo contable)

- En este MVP, la anulación prioriza integridad operativa de inventario (cantidad y trazabilidad).
- El reverso contable formal (asientos y política de recosteo histórico) queda para siguiente etapa.
