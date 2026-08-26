---
id: producto-atributos-impuestos-bodegas
title: "Producto: Atributos, Impuestos y Bodegas"
sidebar_position: 3
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# Producto: Atributos, Impuestos y Bodegas

## Política de Registros Activos (Frontend)

- Mostrar por defecto solo relaciones activas (`producto`, `bodega`, `impuestos`).
- Tratar registros inactivos como historial/borrado lógico.
- Ante inconsistencias de integridad (fracciones inválidas, bodega inactiva), exponer el mensaje funcional de `detail`.

Este documento cubre operaciones especializadas de inventario sobre producto:

- Atributos EAV por producto.
- Impuestos SRI por producto.
- Asignación de producto a bodegas activas.
- Consulta de stock disponible optimizada.
- Transferencias entre bodegas.
- Anulación de movimientos con reverso.

## Atributos EAV de Producto

### PUT `/api/v1/productos/{producto_id}/atributos`

Actualiza/crea en bloque valores EAV del producto (upsert).  
Valida aplicabilidad del atributo según categorías actuales del producto y tipo de dato.

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
    "valor": 42
  }
]
```

  </TabItem>
  <TabItem value="response200" label="Response 200">

```json
[
  {
    "id": "5a4979d6-47ef-46a9-afdc-7b14e72d57df",
    "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
    "atributo_id": "2a2bf5b8-e95e-4f6b-850d-c3ec4ce7c38f",
    "valor_string": "Negro",
    "valor_integer": null,
    "valor_decimal": null,
    "valor_boolean": null,
    "valor_date": null,
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
</Tabs>

### Reglas de Frontend (EAV)

- Tratar `400` como error de validación funcional (no como error técnico).
- No asumir actualización parcial: el batch completo se valida como unidad.
- Mostrar `detail` inline por atributo cuando sea posible.

---

## Impuestos por Producto

### GET `/api/v1/productos/{producto_id}/impuestos`

Lista impuestos activos del catálogo SRI asignados al producto.

### POST `/api/v1/productos/{producto_id}/impuestos`

Asigna impuesto al producto.

- Recibe `impuesto_catalogo_id` y `usuario_auditoria` como **query params**.
- Si ya existe impuesto del mismo tipo (ej. IVA), el anterior se inactiva y se reemplaza.
- El IVA no se puede eliminar, solo reemplazar.

<Tabs>
  <TabItem value="request-post" label="Request POST" default>

```json
{
  "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
  "impuesto_catalogo_id": "41b846bf-6c0a-42a1-9f38-b47e0c937f61",
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response-post" label="Response 201">

```json
{
  "id": "912fa1e3-f7f1-4a2d-bab3-73b4caa263e8",
  "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
  "impuesto_catalogo_id": "41b846bf-6c0a-42a1-9f38-b47e0c937f61",
  "codigo_impuesto_sri": "2",
  "codigo_porcentaje_sri": "4",
  "tarifa": "15.0000",
  "activo": true
}
```

  </TabItem>
</Tabs>

### DELETE `/api/v1/productos/impuestos/{producto_impuesto_id}`

Soft delete de asignación impuesto-producto.

Errores relevantes:

- `400`: intento de eliminar IVA.
- `404`: asignación inexistente o inactiva.

---

## Asignación Producto-Bodega

### POST `/api/v1/productos/{producto_id}/bodegas/{bodega_id}`

Crea asignación de producto a bodega.

Reglas:

- Solo permite bodegas activas.
- Bloquea duplicado producto-bodega.
- Si el producto no permite fracciones, la cantidad debe ser entera.
- Productos tipo `SERVICIO` no pueden tener stock mayor a cero.

### PUT `/api/v1/productos/{producto_id}/bodegas/{bodega_id}`

Actualiza cantidad de la asignación (o crea si no existe).

<Tabs>
  <TabItem value="request-bodega" label="Request" default>

```json
{
  "cantidad": "10.0000",
  "usuario_auditoria": "api"
}
```

  </TabItem>
  <TabItem value="response-bodega" label="Response 200/201">

```json
{
  "id": "7783f5f0-4a44-4db5-8eec-2820a5cce3a0",
  "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
  "bodega_id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
  "cantidad": "10.0000",
  "activo": true
}
```

  </TabItem>
</Tabs>

### GET `/api/v1/productos/{producto_id}/bodegas`

Lista bodegas activas con cantidad referencial del producto.

### GET `/api/v1/bodegas/{bodega_id}/productos`

Lista productos activos asignados a la bodega.

### Regla de borrado de bodega

`DELETE /api/v1/bodegas/{id}` falla con `400` si:

- Tiene productos asignados (`ProductoBodega` activo), o
- Tiene stock materializado mayor a cero.

---

## Stock Disponible (Lectura Optimizada)

### GET `/api/v1/inventarios/stock-disponible`

Consulta de alto rendimiento para POS/reportes operativos.

Parámetros:

- `producto_id` (opcional)
- `bodega_id` (opcional)
- Debe enviarse al menos uno.

Respuesta:

```json
[
  {
    "producto_id": "9c4a9ec6-4e3f-4f7a-8f1a-bf6f7ad0f1aa",
    "producto_nombre": "Laptop Gamer X",
    "bodega_id": "cc723ad4-3f2f-4c25-8229-79a2755ab6f6",
    "codigo_bodega": "BOD-MATRIZ",
    "nombre_bodega": "Bodega Matriz",
    "cantidad_disponible": "20.0000"
  }
]
```

---

## Transferencias entre Bodegas

### POST `/api/v1/inventarios/transferencias`

Ejecuta una transferencia atómica:

1. Egreso en bodega origen (`TRANSFERENCIA`).
2. Ingreso en bodega destino (`INGRESO`) con costo congelado del egreso.

Si falla cualquier parte, se revierte toda la transacción.

<Tabs>
  <TabItem value="request-transfer" label="Request" default>

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

  </TabItem>
  <TabItem value="response-transfer" label="Response 201">

```json
{
  "movimiento_egreso_id": "cb90084a-b0f5-4ede-a455-c14b7496c379",
  "movimiento_ingreso_id": "5ce7434a-f4de-4e43-9d09-6f33e9fd2b4c",
  "bodega_origen_id": "3e044677-f970-48f4-830d-3d325111ab01",
  "bodega_destino_id": "3c697f69-a2dc-46c2-a5fd-74e7862f0fd1",
  "referencia_documento": "TRF-001"
}
```

  </TabItem>
</Tabs>

---

## Anulación de Movimientos

### POST `/api/v1/inventarios/movimientos/{movimiento_id}/anular`

Reglas:

- Si está en `BORRADOR`: solo cambia estado a `ANULADO`.
- Si está en `CONFIRMADO`: genera reverso automático de stock y luego marca `ANULADO`.

Request:

```json
{
  "motivo": "Error de digitación",
  "usuario_auditoria": "api"
}
```

---

## Notas de Integridad

- La cantidad agregada de producto (`Producto.cantidad`) se sincroniza desde stock materializado.
- Si un producto no permite fracciones, cualquier inconsistencia fraccional lanza error de integridad.
- Compras, ventas y anulaciones deben mantener coherencia entre stock materializado y kárdex.

## Contrato Rápido para Frontend (Queries y Errores)

### `GET /api/v1/inventarios/stock-disponible`

| Parámetro | Tipo | Requerido | Regla |
|---|---|---|---|
| `producto_id` | UUID | Condicional | enviar este o `bodega_id` |
| `bodega_id` | UUID | Condicional | enviar este o `producto_id` |

Si no se envía ninguno, retorna `400`.

### Errores de negocio frecuentes

- `400`: cantidad negativa, fracción inválida, producto servicio con stock, filtros insuficientes.
- `404`: producto no encontrado.
- `409`: bodega inactiva o conflicto de asignación.
