---
id: onboarding
title: "Onboarding: Empresa y Configuración Inicial"
sidebar_position: 1
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Onboarding API Common

## Reglas Transversales para Frontend

Antes de integrar los endpoints de onboarding, considera estas reglas de contrato que aplica el backend:

1. Soft delete y filtro `only_active`:
   - `only_active=true`: retorna solo registros activos.
   - `only_active=false`: retorna solo registros inactivos.
2. Códigos HTTP esperados:
   - `400`: error de validación de payload/formato.
   - `404`: recurso no encontrado.
   - `409`: conflicto de integridad (duplicados, FK inválida/inactiva).
3. Efecto colateral al crear empresa:
   - Al crear una `Empresa`, el sistema crea automáticamente una `Sucursal` matriz (`codigo = "001"`, `es_matriz = true`) si no existe.
4. Secuenciales SRI:
   - El endpoint de siguiente secuencial devuelve siempre el número en formato de 9 dígitos (`zfill(9)`), por ejemplo `000000123`.
5. Multiempresa por sesión:
   - El aislamiento por empresa se aplica por contexto de sesión/JWT. Ver detalle en [Empresa Seleccionada por Sesión](./empresa-seleccionada-sesion).

## Política de Registros Activos (Frontend)

- El frontend debe consultar por defecto con `only_active=true` para mostrar únicamente registros activos.
- Los registros inactivos representan **borrado lógico** y no deben mostrarse en flujos operativos normales.
- Para pantallas administrativas de auditoría o recuperación, usar `only_active=false` para consultar inactivos.

## Catálogos y Enums Operativos

### `regimen` (Empresa)

| Valor | Descripción |
|---|---|
| `GENERAL` | Régimen general de contribuyente. |
| `RIMPE_EMPRENDEDOR` | Régimen RIMPE emprendedor. |
| `RIMPE_NEGOCIO_POPULAR` | Régimen RIMPE negocio popular. |

### `modo_emision` (Empresa)

| Valor | Descripción | Regla |
|---|---|---|
| `ELECTRONICO` | Emisión electrónica. | Permitido para todos los regímenes. |
| `NOTA_VENTA_FISICA` | Emisión física (nota de venta). | Solo permitido con `regimen = RIMPE_NEGOCIO_POPULAR`. |

### `tipo_documento` (Secuenciales de Punto de Emisión)

| Valor | Descripción |
|---|---|
| `FACTURA` | Secuencial para facturas. |
| `RETENCION` | Secuencial para retenciones. |
| `NOTA_CREDITO` | Secuencial para notas de crédito. |
| `NOTA_DEBITO` | Secuencial para notas de débito. |
| `GUIA_REMISION` | Secuencial para guías de remisión. |

## GET /api/v1/empresas
Devuelve empresas en forma paginada para inicializar catálogos y configuración de cabecera empresarial en el frontend.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "query": {
    "limit": 50,
    "offset": 0,
    "only_active": true
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "items": [
    {
      "id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90",
      "razon_social": "Comercial Andina",
      "nombre_comercial": "Andina Centro",
      "ruc": "1104680138001",
      "direccion_matriz": "Av. Amazonas N34-451 y Juan Pablo Sanz, Quito",
      "telefono": "022345678",
      "logo": "https://cdn.osiris.local/logo-andina.png",
      "obligado_contabilidad": true,
      "regimen": "GENERAL",
      "modo_emision": "ELECTRONICO",
      "tipo_contribuyente_id": "01",
      "usuario_auditoria": "admin",
      "activo": true
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
<TabItem value="error" label="Error 400">

```json
{
  "detail": [
    {
      "loc": ["query", "limit"],
      "msg": "Input should be greater than or equal to 1",
      "type": "greater_than_equal"
    }
  ]
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| limit | int | No | Tamaño de página. Valor por defecto `50`, mínimo `1`, máximo `1000`. |
| offset | int | No | Desplazamiento inicial. Valor por defecto `0`, mínimo `0`. |
| only_active | bool | No | Si es `true`, solo retorna registros activos. |

## GET /api/v1/empresas/\{item_id\}
Recupera una empresa específica por identificador para consultar configuración tributaria y modo de emisión vigentes.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90",
  "razon_social": "Comercial Andina",
  "nombre_comercial": "Andina Centro",
  "ruc": "1104680138001",
  "direccion_matriz": "Av. Amazonas N34-451 y Juan Pablo Sanz, Quito",
  "telefono": "022345678",
  "logo": "https://cdn.osiris.local/logo-andina.png",
  "obligado_contabilidad": true,
  "regimen": "GENERAL",
  "modo_emision": "ELECTRONICO",
  "tipo_contribuyente_id": "01",
  "usuario_auditoria": "admin",
  "activo": true
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Empresa 3f4bbf20-0192-4cda-a9b9-f2f1615c9d90 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador de la empresa. Si no existe, retorna error de recurso no encontrado. |

## POST /api/v1/empresas
Crea la empresa principal del tenant y valida las reglas tributarias que impactan facturación, emisión y procesos SRI.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "razon_social": "Comercial Andina",
  "nombre_comercial": "Andina Centro",
  "ruc": "1104680138001",
  "direccion_matriz": "Av. Amazonas N34-451 y Juan Pablo Sanz, Quito",
  "telefono": "022345678",
  "logo": "https://cdn.osiris.local/logo-andina.png",
  "obligado_contabilidad": true,
  "regimen": "GENERAL",
  "modo_emision": "ELECTRONICO",
  "tipo_contribuyente_id": "01",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="response" label="Response 201">

```json
{
  "id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90",
  "razon_social": "Comercial Andina",
  "nombre_comercial": "Andina Centro",
  "ruc": "1104680138001",
  "direccion_matriz": "Av. Amazonas N34-451 y Juan Pablo Sanz, Quito",
  "telefono": "022345678",
  "logo": "https://cdn.osiris.local/logo-andina.png",
  "obligado_contabilidad": true,
  "regimen": "GENERAL",
  "modo_emision": "ELECTRONICO",
  "tipo_contribuyente_id": "01",
  "usuario_auditoria": "admin",
  "activo": true
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "NOTA_VENTA_FISICA solo está permitido para régimen RIMPE_NEGOCIO_POPULAR."
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| razon_social | string | Sí | Solo letras y espacios. Regex `^[A-Za-zÁÉÍÓÚÑáéíóúñ\s]+$`. |
| nombre_comercial | string | No | Letras, números y `.,-`. Regex `^[A-Za-zÁÉÍÓÚÑáéíóúñ0-9\s\.\,\-]+$`. |
| ruc | string | Sí | Debe tener exactamente 13 dígitos y pasar validación de identificación. |
| direccion_matriz | string | Sí | Dirección legal principal de la empresa. |
| telefono | string | No | Solo dígitos, entre 7 y 10 caracteres. |
| logo | string | No | URL o referencia del logo. |
| obligado_contabilidad | boolean | No | Valor por defecto `false`. |
| regimen | enum | No | Valor por defecto `GENERAL`. |
| modo_emision | enum | No | Valor por defecto `ELECTRONICO`; `NOTA_VENTA_FISICA` exige `RIMPE_NEGOCIO_POPULAR`. |
| tipo_contribuyente_id | string | Sí | Código de 2 caracteres exactos. |
| usuario_auditoria | string | Sí | Usuario que registra la operación. |

## PUT /api/v1/empresas/\{item_id\}
Actualiza parcialmente la configuración empresarial para ajustar reglas fiscales sin recrear el registro.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90"
  },
  "body": {
    "nombre_comercial": "Andina Centro Norte",
    "telefono": "022456789",
    "modo_emision": "ELECTRONICO",
    "usuario_auditoria": "supervisor"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90",
  "razon_social": "Comercial Andina",
  "nombre_comercial": "Andina Centro Norte",
  "ruc": "1104680138001",
  "direccion_matriz": "Av. Amazonas N34-451 y Juan Pablo Sanz, Quito",
  "telefono": "022456789",
  "logo": "https://cdn.osiris.local/logo-andina.png",
  "obligado_contabilidad": true,
  "regimen": "GENERAL",
  "modo_emision": "ELECTRONICO",
  "tipo_contribuyente_id": "01",
  "usuario_auditoria": "supervisor",
  "activo": true
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "El RUC ingresado no es válido."
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador de la empresa a actualizar. |
| razon_social | string | No | Si se envía, respeta regex de solo letras y espacios. |
| nombre_comercial | string | No | Si se envía, respeta regex alfanumérico con signos `.,-`. |
| ruc | string | No | Si se envía, debe tener 13 dígitos y validación de identificación. |
| direccion_matriz | string | No | Nueva dirección matriz. |
| telefono | string | No | Solo dígitos, entre 7 y 10 caracteres. |
| logo | string | No | URL o referencia del logo. |
| obligado_contabilidad | boolean | No | Marca contable de la empresa. |
| regimen | enum | No | Régimen tributario de la empresa. |
| modo_emision | enum | No | Si se combina con régimen no permitido dispara error de negocio. |
| tipo_contribuyente_id | string | No | Código de 2 caracteres. |
| usuario_auditoria | string | No | Usuario que realiza el cambio. |

## DELETE /api/v1/empresas/\{item_id\}
Realiza baja lógica de una empresa para retirar su uso operativo sin borrar historial.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 204">

```json
null
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Empresa 3f4bbf20-0192-4cda-a9b9-f2f1615c9d90 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador de la empresa a desactivar. |

## GET /api/v1/sucursales
Lista sucursales para selección operativa por bodega, ventas y punto de facturación.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "query": {
    "limit": 50,
    "offset": 0,
    "only_active": true
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "items": [
    {
      "id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c",
      "codigo": "001",
      "nombre": "Matriz Quito",
      "direccion": "Av. 6 de Diciembre N25-56 y Colón, Quito",
      "telefono": "022234567",
      "latitud": -0.197326,
      "longitud": -78.490119,
      "es_matriz": true,
      "usuario_auditoria": "admin",
      "empresa_id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90",
      "activo": true,
      "creado_en": "2026-02-23T15:20:00Z",
      "actualizado_en": "2026-02-23T15:20:00Z"
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
<TabItem value="error" label="Error 400">

```json
{
  "detail": [
    {
      "loc": ["query", "offset"],
      "msg": "Input should be greater than or equal to 0",
      "type": "greater_than_equal"
    }
  ]
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| limit | int | No | Tamaño de página. Default `50`, mínimo `1`, máximo `1000`. |
| offset | int | No | Inicio de paginación. Default `0`, mínimo `0`. |
| only_active | bool | No | Filtra por registros activos cuando es `true`. |

## GET /api/v1/sucursales/\{item_id\}
Obtiene una sucursal por ID para recuperar datos de ubicación, matriz y auditoría operativa.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c",
  "codigo": "001",
  "nombre": "Matriz Quito",
  "direccion": "Av. 6 de Diciembre N25-56 y Colón, Quito",
  "telefono": "022234567",
  "latitud": -0.197326,
  "longitud": -78.490119,
  "es_matriz": true,
  "usuario_auditoria": "admin",
  "empresa_id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90",
  "activo": true,
  "creado_en": "2026-02-23T15:20:00Z",
  "actualizado_en": "2026-02-23T15:20:00Z"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Sucursal 0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador único de la sucursal. |

## POST /api/v1/sucursales
Crea sucursales de operación y aplica reglas estructurales de código, matriz y georreferenciación.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "codigo": "001",
  "nombre": "Matriz Quito",
  "direccion": "Av. 6 de Diciembre N25-56 y Colón, Quito",
  "telefono": "022234567",
  "latitud": -0.197326,
  "longitud": -78.490119,
  "es_matriz": true,
  "usuario_auditoria": "admin",
  "empresa_id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90"
}
```

</TabItem>
<TabItem value="response" label="Response 201">

```json
{
  "id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c",
  "codigo": "001",
  "nombre": "Matriz Quito",
  "direccion": "Av. 6 de Diciembre N25-56 y Colón, Quito",
  "telefono": "022234567",
  "latitud": -0.197326,
  "longitud": -78.490119,
  "es_matriz": true,
  "usuario_auditoria": "admin",
  "empresa_id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90",
  "activo": true,
  "creado_en": "2026-02-23T15:20:00Z",
  "actualizado_en": "2026-02-23T15:20:00Z"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "La sucursal matriz debe tener código '001' y las demás no pueden marcarse como matriz"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| codigo | string | Sí | Longitud exacta de 3 caracteres; combinado con `empresa_id` debe ser único. |
| nombre | string | Sí | Longitud entre 3 y 50 caracteres. |
| direccion | string | Sí | Longitud entre 3 y 100 caracteres. |
| telefono | string | No | Solo dígitos, entre 7 y 10 caracteres. |
| latitud | decimal | No | Si se envía, debe estar entre `-90` y `90`. |
| longitud | decimal | No | Si se envía, debe estar entre `-180` y `180`. |
| es_matriz | boolean | Sí | Si `true`, el `codigo` debe ser `001`; si `false`, el código no puede ser `001`. |
| usuario_auditoria | string | Sí | Usuario responsable del registro. |
| empresa_id | UUID | Sí | Empresa propietaria de la sucursal; debe existir y estar activa. |

## PUT /api/v1/sucursales/\{item_id\}
Actualiza datos de sucursal para mantener operación comercial sin perder trazabilidad histórica.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c"
  },
  "body": {
    "nombre": "Matriz Quito Norte",
    "direccion": "Av. Naciones Unidas y República de El Salvador, Quito",
    "telefono": "022998877",
    "latitud": -0.176125,
    "longitud": -78.482531,
    "usuario_auditoria": "supervisor"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c",
  "codigo": "001",
  "nombre": "Matriz Quito Norte",
  "direccion": "Av. Naciones Unidas y República de El Salvador, Quito",
  "telefono": "022998877",
  "latitud": -0.176125,
  "longitud": -78.482531,
  "es_matriz": true,
  "usuario_auditoria": "supervisor",
  "empresa_id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90",
  "activo": true,
  "creado_en": "2026-02-23T15:20:00Z",
  "actualizado_en": "2026-02-23T16:05:00Z"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "La latitud debe estar entre -90 y 90"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador de la sucursal a modificar. |
| nombre | string | No | Si se envía, longitud entre 3 y 50 caracteres. |
| direccion | string | No | Si se envía, longitud entre 3 y 100 caracteres. |
| telefono | string | No | Si se envía, solo dígitos entre 7 y 10 caracteres. |
| latitud | decimal | No | Debe ser decimal válido y quedar en el rango `-90` a `90`. |
| longitud | decimal | No | Debe ser decimal válido y quedar en el rango `-180` a `180`. |
| es_matriz | boolean | No | Debe respetar la regla con `codigo` (`001` para matriz). |
| activo | boolean | No | Permite activar o desactivar la sucursal. |
| usuario_auditoria | string | No | Si se envía, entre 3 y 50 caracteres. |

## DELETE /api/v1/sucursales/\{item_id\}
Desactiva una sucursal para detener su uso en nuevas operaciones sin eliminar su histórico.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 204">

```json
null
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Sucursal 0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador de la sucursal a desactivar. |

## GET /api/v1/puntos-emision
Lista puntos de emisión para facturación y control de secuenciales por establecimiento.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "query": {
    "limit": 50,
    "offset": 0,
    "only_active": true
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "items": [
    {
      "id": "3f95bc01-4f67-4d0a-8119-11f39215bca0",
      "codigo": "002",
      "descripcion": "Caja Principal Quito",
      "secuencial_actual": 1,
      "config_impresion": {
        "margen_superior_cm": 5.0,
        "max_items_por_pagina": 15
      },
      "usuario_auditoria": "admin",
      "sucursal_id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c",
      "activo": true,
      "creado_en": "2026-02-23T16:10:00Z",
      "actualizado_en": "2026-02-23T16:10:00Z"
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
<TabItem value="error" label="Error 400">

```json
{
  "detail": [
    {
      "loc": ["query", "limit"],
      "msg": "Input should be less than or equal to 1000",
      "type": "less_than_equal"
    }
  ]
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| limit | int | No | Tamaño de página. Default `50`, mínimo `1`, máximo `1000`. |
| offset | int | No | Inicio de paginación. Default `0`, mínimo `0`. |
| only_active | bool | No | Filtra puntos de emisión activos. |

## GET /api/v1/puntos-emision/\{item_id\}
Consulta el detalle de un punto de emisión para operación de caja y configuración de impresión.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "3f95bc01-4f67-4d0a-8119-11f39215bca0"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "3f95bc01-4f67-4d0a-8119-11f39215bca0",
  "codigo": "002",
  "descripcion": "Caja Principal Quito",
  "secuencial_actual": 1,
  "config_impresion": {
    "margen_superior_cm": 5.0,
    "max_items_por_pagina": 15
  },
  "usuario_auditoria": "admin",
  "sucursal_id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c",
  "activo": true,
  "creado_en": "2026-02-23T16:10:00Z",
  "actualizado_en": "2026-02-23T16:10:00Z"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Punto-emision 3f95bc01-4f67-4d0a-8119-11f39215bca0 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador del punto de emisión. |

## POST /api/v1/puntos-emision
Registra un nuevo punto de emisión por sucursal para separar series documentales y comportamiento de impresión.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "codigo": "002",
  "descripcion": "Caja Principal Quito",
  "secuencial_actual": 1,
  "config_impresion": {
    "margen_superior_cm": 5.0,
    "max_items_por_pagina": 15
  },
  "usuario_auditoria": "admin",
  "sucursal_id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c"
}
```

</TabItem>
<TabItem value="response" label="Response 201">

```json
{
  "id": "3f95bc01-4f67-4d0a-8119-11f39215bca0",
  "codigo": "002",
  "descripcion": "Caja Principal Quito",
  "secuencial_actual": 1,
  "config_impresion": {
    "margen_superior_cm": 5.0,
    "max_items_por_pagina": 15
  },
  "usuario_auditoria": "admin",
  "sucursal_id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c",
  "activo": true,
  "creado_en": "2026-02-23T16:10:00Z",
  "actualizado_en": "2026-02-23T16:10:00Z"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Error de integridad al guardar"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| codigo | string | Sí | Longitud exacta de 3 caracteres; con `sucursal_id` debe ser único. |
| descripcion | string | Sí | Descripción funcional del punto de emisión. En persistencia admite hasta 120 caracteres. |
| secuencial_actual | int | No | Default `1`, mínimo `1`. |
| config_impresion | object | No | Objeto JSON; default `{margen_superior_cm: 5.0, max_items_por_pagina: 15}`. |
| usuario_auditoria | string | Sí | Usuario que registra la operación. |
| sucursal_id | UUID | Sí | Sucursal propietaria del punto; debe existir y estar activa. |

## PUT /api/v1/puntos-emision/\{item_id\}
Actualiza descripción, secuencial base o configuración de impresión para ajustar la operación diaria de caja.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "3f95bc01-4f67-4d0a-8119-11f39215bca0"
  },
  "body": {
    "descripcion": "Caja Principal Quito - Turno A",
    "secuencial_actual": 25,
    "config_impresion": {
      "margen_superior_cm": 4.5,
      "max_items_por_pagina": 18
    },
    "usuario_auditoria": "supervisor",
    "activo": true
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "3f95bc01-4f67-4d0a-8119-11f39215bca0",
  "codigo": "002",
  "descripcion": "Caja Principal Quito - Turno A",
  "secuencial_actual": 25,
  "config_impresion": {
    "margen_superior_cm": 4.5,
    "max_items_por_pagina": 18
  },
  "usuario_auditoria": "supervisor",
  "sucursal_id": "0c8cd2cb-4ab6-4382-bad9-c8a2e75f8a2c",
  "activo": true,
  "creado_en": "2026-02-23T16:10:00Z",
  "actualizado_en": "2026-02-23T16:22:00Z"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": [
    {
      "loc": ["body", "secuencial_actual"],
      "msg": "Input should be greater than or equal to 1",
      "type": "greater_than_equal"
    }
  ]
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador del punto de emisión a actualizar. |
| descripcion | string | No | Texto descriptivo del punto de emisión. |
| secuencial_actual | int | No | Valor base del secuencial del punto en documento factura. |
| config_impresion | object | No | Parámetros de impresión usados por formatos de salida. |
| usuario_auditoria | string | No | Usuario responsable de la modificación. |
| activo | boolean | No | Activa o desactiva el punto de emisión. |

## DELETE /api/v1/puntos-emision/\{item_id\}
Ejecuta baja lógica de un punto de emisión para impedir nuevas transacciones con esa serie.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "3f95bc01-4f67-4d0a-8119-11f39215bca0"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 204">

```json
null
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Punto-emision 3f95bc01-4f67-4d0a-8119-11f39215bca0 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador del punto de emisión a desactivar. |

## POST /api/v1/puntos-emision/\{punto_emision_id\}/secuenciales/\{tipo_documento\}/siguiente
Entrega y consume el siguiente secuencial SRI de forma transaccional por punto y tipo documental.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "punto_emision_id": "3f95bc01-4f67-4d0a-8119-11f39215bca0",
    "tipo_documento": "FACTURA"
  },
  "body": {
    "usuario_auditoria": "cajero01"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "secuencial": "000000026"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Punto de emision no encontrado o inactivo"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| punto_emision_id | UUID | Sí | Punto de emisión sobre el que se controla secuencial. |
| tipo_documento | enum | Sí | Valores permitidos: `FACTURA`, `RETENCION`, `NOTA_CREDITO`, `NOTA_DEBITO`, `GUIA_REMISION`. |
| usuario_auditoria | string | No | Usuario opcional para trazabilidad del incremento. |

## POST /api/v1/puntos-emision/\{punto_emision_id\}/secuenciales/\{tipo_documento\}/ajuste-manual
Permite corregir manualmente secuenciales en contingencias con control estricto de perfil administrativo y permisos.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "punto_emision_id": "3f95bc01-4f67-4d0a-8119-11f39215bca0",
    "tipo_documento": "FACTURA"
  },
  "body": {
    "usuario_id": "f18b9122-5531-41d1-89b2-ec18f9b40b21",
    "justificacion": "Ajuste por contingencia y salto controlado de numeración autorizado.",
    "nuevo_secuencial": 120
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "f8406d11-2f03-4b08-9e0d-2f9f0138dd48",
  "punto_emision_id": "3f95bc01-4f67-4d0a-8119-11f39215bca0",
  "tipo_documento": "FACTURA",
  "secuencial_actual": 120,
  "usuario_auditoria": "f18b9122-5531-41d1-89b2-ec18f9b40b21",
  "activo": true,
  "creado_en": "2026-02-23T16:12:00Z",
  "actualizado_en": "2026-02-23T16:35:00Z"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Solo un administrador puede ajustar secuenciales"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| punto_emision_id | UUID | Sí | Identificador del punto de emisión cuyo secuencial se corrige. |
| tipo_documento | enum | Sí | Tipo documental SRI a ajustar: `FACTURA`, `RETENCION`, `NOTA_CREDITO`, `NOTA_DEBITO`, `GUIA_REMISION`. |
| usuario_id | UUID | Sí | Usuario que ejecuta el ajuste; debe estar activo, tener rol `ADMIN/ADMINISTRADOR` y permiso de módulo `PUNTOS_EMISION` para `actualizar`. |
| justificacion | string | Sí | Texto obligatorio entre 5 y 500 caracteres, se registra en auditoría. |
| nuevo_secuencial | int | Sí | Nuevo valor del secuencial, mínimo `1`. |

---

## Matriz de Errores por Endpoint

> Códigos operativos para manejo de UX y mensajes en frontend.

| Endpoint | Códigos esperados |
|---|---|
| `GET /api/v1/empresas` | `200`, `422` |
| `GET /api/v1/empresas/{item_id}` | `200`, `404` |
| `POST /api/v1/empresas` | `201`, `400`, `404`, `409`, `422` |
| `PUT /api/v1/empresas/{item_id}` | `200`, `400`, `404`, `409`, `422` |
| `DELETE /api/v1/empresas/{item_id}` | `204`, `404` |
| `GET /api/v1/sucursales` | `200`, `422` |
| `GET /api/v1/sucursales/{item_id}` | `200`, `404` |
| `POST /api/v1/sucursales` | `201`, `400`, `404`, `409`, `422` |
| `PUT /api/v1/sucursales/{item_id}` | `200`, `400`, `404`, `409`, `422` |
| `DELETE /api/v1/sucursales/{item_id}` | `204`, `404` |
| `GET /api/v1/puntos-emision` | `200`, `422` |
| `GET /api/v1/puntos-emision/{item_id}` | `200`, `404` |
| `POST /api/v1/puntos-emision` | `201`, `404`, `409`, `422` |
| `PUT /api/v1/puntos-emision/{item_id}` | `200`, `404`, `409`, `422` |
| `DELETE /api/v1/puntos-emision/{item_id}` | `204`, `404` |
| `POST /api/v1/puntos-emision/{punto_emision_id}/secuenciales/{tipo_documento}/siguiente` | `200`, `404`, `422` |
| `POST /api/v1/puntos-emision/{punto_emision_id}/secuenciales/{tipo_documento}/ajuste-manual` | `200`, `400`, `403`, `404`, `422` |
