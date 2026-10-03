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

Los tipos admitidos son `string`, `integer`, `decimal`, `boolean`, `date`, `select` y `catalog`. `select` guarda la opción configurada en `valor_string`; `catalog` referencia un catálogo común y solo admite valores activos. Los atributos numéricos pueden declarar `allow_negative`, `min_value` y `max_value`. Al omitir un valor requerido, el backend persiste el default tipado de la asignación de categoría.

Los cambios de tipo convierten automáticamente los valores compatibles. Los no convertibles conservan el valor original y generan remapeos pendientes auditables:

- `GET /api/v1/atributos/remapeos/pendientes`
- `POST /api/v1/atributos/remapeos/resolver` con `assignments: [{"id": "<remapeo UUID>", "valor": "<valor válido>"}]`

Catálogos configurables:

- `GET /api/v1/catalogos`
- `GET /api/v1/catalogos/{catalog_id}/valores?include_inactive=false`
- `POST /api/v1/catalogos` crea un catálogo y `PATCH /api/v1/catalogos/{catalog_id}` cambia nombre/descripción.
- `DELETE /api/v1/catalogos/{catalog_id}` da de baja el catálogo; se rechaza si algún atributo activo lo referencia.
- `POST /api/v1/catalogos/{catalog_id}/valores` agrega/reactiva un valor y `PATCH /api/v1/catalogos/{catalog_id}/valores/{value_id}` lo renombra.
- `POST /api/v1/catalogos/{catalog_id}/valores/{value_id}/deactivate` y `POST /api/v1/catalogos/{catalog_id}/valores/{value_id}/reactivate` controlan el estado del valor.

Todas las escrituras de catálogo requieren rol `admin` o `supervisor`.

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

## Categorías temporales y recategorización

La categoría B3 `Sin clasificar` es una hija temporal marcada con `is_default`; no admite asignación directa de productos y se desactiva al quedar vacía.

- `GET /api/v1/categorias/sin-clasificar/conteo` devuelve `{ "count": N }` en el scope empresarial autenticado.
- `GET /api/v1/categorias/sin-clasificar/productos` lista productos pendientes solo de la empresa activa.
- `POST /api/v1/categorias/recategorizar` acepta `assignments: [{"producto_id": "UUID", "categoria_id": "UUID"}]`; el destino debe ser hoja activa en la misma rama y empresa.
- `DELETE /api/v1/categorias/{id}?confirmar_baja_productos=true` solo permite cascada de productos sin stock y exige confirmación.
- Al mover una categoría con colisión de atributos, el backend responde `CATEGORY_ATTRIBUTE_COLLISION_REQUIRES_CONFIRMATION`; repetir con `confirmar_limpieza_colision=true` limpia solo los valores heredados desplazados y audita el antes/después.

---

## Impuestos por Producto

Las asignaciones pertenecen a un perfil `(empresa, producto)`. La empresa se obtiene de la sesión autenticada; un `empresa_id` del cliente no define el alcance. El perfil admite exactamente un IVA y un ICE opcional, ambos activos, vigentes, configurados en `Empresa.impuesto_catalogo_ids` y compatibles con `BIEN/SERVICIO`.

`GET /api/v1/productos/impuestos-disponibles?tipo_producto=BIEN|SERVICIO` devuelve solo los impuestos seleccionables de la empresa activa. Para reemplazar el perfil, `PUT /api/v1/productos/{producto_id}` incluye `impuesto_catalogo_ids` con el conjunto completo; lista vacía, duplicados o IRBPNR se rechazan. Compras y ventas copian este perfil a snapshots; esos documentos históricos no se recalculan.

Antes de aplicar la revisión Alembic `a73f2c9d1e60`, ejecutar `scripts/audit_product_tax_company_scope.py` y conciliar manualmente toda asignación **activa** marcada para revisión. La migración bloquea con IDs si encuentra asignaciones activas sin empresa o con impuesto no configurado; no reasigna perfiles ni agrega los impuestos legacy a la whitelist. En development, las 24 relaciones legacy fuera de whitelist pertenecían a productos de prueba y se inactivaron junto con los 19 productos; las filas se conservan como historial sin empresa. La migración añadió el IVA 0% canónico vigente requerido por 2.2 y la preflight ignora relaciones inactivas.

### GET `/api/v1/productos/{producto_id}/impuestos`

Lista los impuestos activos asignados al producto dentro de la empresa autenticada. No utiliza un fallback global.

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

## Proveedores de Producto

- `PUT /api/v1/productos/{producto_id}/proveedores-persona` reemplaza la lista de proveedores persona usando `{"proveedor_ids": ["UUID", ...]}`.
- `PUT /api/v1/productos/{producto_id}/proveedores-sociedad` reemplaza la lista de proveedores sociedad con el mismo contrato.

Ambas operaciones requieren un rol de producto (`admin`, `operator` o `supervisor`) y validan que cada proveedor exista y esté activo.

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
