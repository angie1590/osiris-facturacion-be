---
id: seguridad-accesos
title: "Seguridad y Accesos"
sidebar_position: 2
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Common - Seguridad y Accesos

## Esquema de Autenticación Recomendado

Según la arquitectura actual (`main.py` + `audit_context.py`):

- El backend soporta cabeceras para resolver identidad y contexto de empresa:
  - `Authorization: Bearer <token>`
  - `X-User-Id: <uuid>`
  - `X-Empresa-Id: <uuid>`
- **Recomendación para frontend productivo**: usar `Authorization: Bearer <JWT>` como mecanismo principal.
- `X-User-Id` y `X-Empresa-Id` deben quedar para pruebas técnicas, smoke tests o integraciones internas controladas.
- Comportamiento por entorno (`ENVIRONMENT`):
  - `development|dev|test|testing|local|ci`: se permiten headers auxiliares (`X-User-Id`, `X-Empresa-Id`).
  - `production`: headers auxiliares se ignoran; se exige `Authorization`.
- En endpoints sensibles, si no existe identidad o permisos suficientes, el sistema retorna `403` y registra evento `UNAUTHORIZED_ACCESS`.
- Para el contrato completo de multiempresa por sesión, revisar: [Empresa Seleccionada por Sesión](./empresa-seleccionada-sesion).

## Política de Registros Activos (Frontend)

- El frontend debe consultar por defecto con `only_active=true` para mostrar cuentas y catálogos vigentes.
- `only_active=false` retorna registros inactivos (borrado lógico) para módulos administrativos.

## GET /api/v1/usuarios
Lista usuarios de forma paginada para administración de accesos y gobierno de cuentas.

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
      "id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58",
      "persona_id": "322cd8eb-f85a-4a6a-8f75-108709f8c655",
      "rol_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
      "username": "j.perez",
      "requiere_cambio_password": true,
      "activo": true,
      "creado_en": "2026-02-23T10:30:00Z",
      "actualizado_en": "2026-02-23T10:30:00Z",
      "usuario_auditoria": "admin"
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
| offset | int | No | Desplazamiento inicial. Default `0`, mínimo `0`. |
| only_active | bool | No | Si es `true`, devuelve solo usuarios activos. |

## GET /api/v1/usuarios/\{item_id\}
Obtiene el detalle de una cuenta para auditoría, soporte y validación de asignación de rol.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58",
  "persona_id": "322cd8eb-f85a-4a6a-8f75-108709f8c655",
  "rol_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
  "username": "j.perez",
  "requiere_cambio_password": true,
  "activo": true,
  "creado_en": "2026-02-23T10:30:00Z",
  "actualizado_en": "2026-02-23T10:30:00Z",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Usuario b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador del usuario. Si no existe, retorna no encontrado. |

## POST /api/v1/usuarios
Crea un usuario operativo, valida referencias activas y almacena la contraseña en hash.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "persona_id": "322cd8eb-f85a-4a6a-8f75-108709f8c655",
  "rol_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
  "username": "j.perez",
  "password": "ClaveSegura2026",
  "requiere_cambio_password": true,
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="response" label="Response 201">

```json
{
  "id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58",
  "persona_id": "322cd8eb-f85a-4a6a-8f75-108709f8c655",
  "rol_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
  "username": "j.perez",
  "requiere_cambio_password": true,
  "activo": true,
  "creado_en": "2026-02-23T10:30:00Z",
  "actualizado_en": "2026-02-23T10:30:00Z",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "La contraseña es obligatoria"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| persona_id | UUID | Sí | Debe existir y estar activa; además es única por usuario. |
| rol_id | UUID | Sí | Debe existir y estar activo. |
| username | string | Sí | Único a nivel sistema. Máximo 120 caracteres en persistencia. |
| password | string | Sí | Mínimo 6 caracteres; se transforma a `password_hash`. |
| requiere_cambio_password | bool | No | Default `true`. Fuerza cambio en primer ingreso. |
| usuario_auditoria | string | Sí | Usuario que registra la operación. |

## PUT /api/v1/usuarios/\{item_id\}
Actualiza solo rol, contraseña o auditoría de una cuenta sin cambiar identidad base del usuario.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58"
  },
  "body": {
    "rol_id": "9ee25f03-4760-4b7a-a3bf-4f48f93f4cc7",
    "password": "NuevaClaveFuerte2026",
    "usuario_auditoria": "seguridad"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58",
  "persona_id": "322cd8eb-f85a-4a6a-8f75-108709f8c655",
  "rol_id": "9ee25f03-4760-4b7a-a3bf-4f48f93f4cc7",
  "username": "j.perez",
  "requiere_cambio_password": true,
  "activo": true,
  "creado_en": "2026-02-23T10:30:00Z",
  "actualizado_en": "2026-02-23T11:00:00Z",
  "usuario_auditoria": "seguridad"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": [
    {
      "loc": ["body", "password"],
      "msg": "String should have at least 6 characters",
      "type": "string_too_short"
    }
  ]
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador del usuario a actualizar. |
| rol_id | UUID | No | Si se envía, debe existir y estar activo. |
| password | string | No | Si se envía, mínimo 6 caracteres; se guarda como hash. |
| usuario_auditoria | string | No | Usuario que ejecuta la modificación. |

## DELETE /api/v1/usuarios/\{item_id\}
Aplica baja lógica de usuario para bloquear su operación sin perder trazabilidad histórica.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58"
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
  "detail": "Usuario b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador del usuario a desactivar. |

## GET /api/v1/usuarios/\{usuario_id\}/permisos
Retorna el conjunto de permisos por módulo según el rol del usuario para decisiones de autorización en frontend y backend.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "usuario_id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
[
  {
    "codigo": "INVENTARIO",
    "nombre": "Inventario",
    "puede_leer": true,
    "puede_crear": true,
    "puede_actualizar": true,
    "puede_eliminar": false
  },
  {
    "codigo": "COMPRAS",
    "nombre": "Compras",
    "puede_leer": true,
    "puede_crear": false,
    "puede_actualizar": false,
    "puede_eliminar": false
  }
]
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Usuario no encontrado"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| usuario_id | UUID | Sí | Usuario objetivo para resolver permisos por rol asociado. |

## GET /api/v1/usuarios/\{usuario_id\}/menu
Retorna únicamente módulos visibles en menú para el usuario (solo permisos con lectura habilitada).

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "usuario_id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
[
  {
    "codigo": "INVENTARIO",
    "nombre": "Inventario",
    "puede_leer": true,
    "puede_crear": true,
    "puede_actualizar": true,
    "puede_eliminar": false
  }
]
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Usuario no encontrado"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| usuario_id | UUID | Sí | Usuario para construir menú dinámico por rol y permisos activos. |

## POST /api/v1/usuarios/\{usuario_id\}/reset-password
Regenera una contraseña temporal para recuperación segura y marca la cuenta para cambio obligatorio al siguiente inicio de sesión.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "usuario_id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58"
  },
  "body": {
    "usuario_auditoria": "soporte"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "usuario_id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58",
  "username": "j.perez",
  "password_temporal": "Ab12Cd34Ef56",
  "requiere_cambio_password": true
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Usuario inactivo"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| usuario_id | UUID | Sí | Identificador del usuario a resetear. |
| usuario_auditoria | string | No | Usuario que deja evidencia de la operación. |

## POST /api/v1/usuarios/\{usuario_id\}/verify-password
Verifica si una clave en texto plano coincide con la contraseña actual del usuario.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "usuario_id": "b7ec7d8d-1a3f-4a90-a84f-5d9b73a5ed58"
  },
  "body": {
    "password": "ClaveSegura2026"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
true
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Usuario no encontrado"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| usuario_id | UUID | Sí | Usuario sobre el cual se valida la contraseña. |
| password | string | Sí | Clave a verificar. Mínimo 1 carácter. |

---

## GET /api/v1/roles
Lista roles para la matriz de seguridad y asignación de perfiles operativos.

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
      "id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
      "nombre": "ADMIN_INVENTARIO",
      "descripcion": "Administra inventario y catálogos relacionados",
      "activo": true,
      "creado_en": "2026-02-23T09:00:00Z",
      "actualizado_en": "2026-02-23T09:00:00Z",
      "usuario_auditoria": "admin"
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
| only_active | bool | No | Filtra roles activos si es `true`. |

## GET /api/v1/roles/\{item_id\}
Obtiene un rol específico para consultar su definición y estado operativo.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
  "nombre": "ADMIN_INVENTARIO",
  "descripcion": "Administra inventario y catálogos relacionados",
  "activo": true,
  "creado_en": "2026-02-23T09:00:00Z",
  "actualizado_en": "2026-02-23T09:00:00Z",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Role 7ebca6cc-5c68-4600-bf7f-0a64b482f6e8 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador del rol. |

## POST /api/v1/roles
Crea un rol nuevo para modelar perfiles de autorización en la plataforma.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "nombre": "ADMIN_INVENTARIO",
  "descripcion": "Administra inventario y catálogos relacionados",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="response" label="Response 201">

```json
{
  "id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
  "nombre": "ADMIN_INVENTARIO",
  "descripcion": "Administra inventario y catálogos relacionados",
  "activo": true,
  "creado_en": "2026-02-23T09:00:00Z",
  "actualizado_en": "2026-02-23T09:00:00Z",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Registro duplicado: el valor de 'nombre' ya existe."
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| nombre | string | Sí | Nombre único del rol. Máximo 120 caracteres en persistencia. |
| descripcion | string | No | Descripción funcional del rol. Máximo 255 caracteres. |
| usuario_auditoria | string | No | Usuario que crea el registro. |

## PUT /api/v1/roles/\{item_id\}
Actualiza nombre o descripción de un rol para evolucionar políticas de acceso.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8"
  },
  "body": {
    "descripcion": "Administra inventario, bodegas y transferencias",
    "usuario_auditoria": "seguridad"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
  "nombre": "ADMIN_INVENTARIO",
  "descripcion": "Administra inventario, bodegas y transferencias",
  "activo": true,
  "creado_en": "2026-02-23T09:00:00Z",
  "actualizado_en": "2026-02-23T09:40:00Z",
  "usuario_auditoria": "seguridad"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Role 7ebca6cc-5c68-4600-bf7f-0a64b482f6e8 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Rol objetivo de la actualización. |
| nombre | string | No | Si se envía, mantiene unicidad y máximo 120 caracteres. |
| descripcion | string | No | Si se envía, máximo 255 caracteres. |
| usuario_auditoria | string | No | Usuario que ejecuta el cambio. |

## DELETE /api/v1/roles/\{item_id\}
Desactiva un rol para retirarlo de uso operativo conservando su historial.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8"
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
  "detail": "Role 7ebca6cc-5c68-4600-bf7f-0a64b482f6e8 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador del rol a desactivar. |

---

## GET /api/v1/modulos
Lista módulos funcionales para configuración de menú y matriz de permisos.

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
      "id": "e3fd8028-9f47-4bc2-9e4c-e889b592ef8d",
      "codigo": "INVENTARIO",
      "nombre": "Inventario",
      "descripcion": "Gestión de productos, bodegas y movimientos",
      "orden": 2,
      "icono": "boxes",
      "activo": true,
      "creado_en": "2026-02-23T08:45:00Z",
      "actualizado_en": "2026-02-23T08:45:00Z",
      "usuario_auditoria": "admin"
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
| limit | int | No | Tamaño de página. Default `50`, mínimo `1`, máximo `1000`. |
| offset | int | No | Desplazamiento inicial. Default `0`, mínimo `0`. |
| only_active | bool | No | Si es `true`, solo devuelve módulos activos. |

## GET /api/v1/modulos/\{item_id\}
Obtiene el detalle de un módulo para administración de navegación y seguridad.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "e3fd8028-9f47-4bc2-9e4c-e889b592ef8d"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "e3fd8028-9f47-4bc2-9e4c-e889b592ef8d",
  "codigo": "INVENTARIO",
  "nombre": "Inventario",
  "descripcion": "Gestión de productos, bodegas y movimientos",
  "orden": 2,
  "icono": "boxes",
  "activo": true,
  "creado_en": "2026-02-23T08:45:00Z",
  "actualizado_en": "2026-02-23T08:45:00Z",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Módulo e3fd8028-9f47-4bc2-9e4c-e889b592ef8d not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador del módulo. |

## POST /api/v1/modulos
Crea un módulo de negocio para habilitar su uso en menús y autorización por rol.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "codigo": "SEGURIDAD",
  "nombre": "Seguridad y Accesos",
  "descripcion": "Gestión de usuarios, roles y permisos",
  "orden": 1,
  "icono": "shield",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="response" label="Response 201">

```json
{
  "id": "3f8bd45e-aaea-4d53-be8e-c3ed303e4025",
  "codigo": "SEGURIDAD",
  "nombre": "Seguridad y Accesos",
  "descripcion": "Gestión de usuarios, roles y permisos",
  "orden": 1,
  "icono": "shield",
  "activo": true,
  "creado_en": "2026-02-23T08:50:00Z",
  "actualizado_en": "2026-02-23T08:50:00Z",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Registro duplicado: el valor de 'codigo' ya existe."
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| codigo | string | Sí | Código único del módulo. Máximo 50 caracteres. |
| nombre | string | Sí | Nombre descriptivo del módulo. Máximo 120 caracteres. |
| descripcion | string | No | Texto descriptivo. Máximo 255 caracteres. |
| orden | int | No | Orden de despliegue en menú. |
| icono | string | No | Nombre de icono para frontend. Máximo 50 caracteres. |
| usuario_auditoria | string | No | Usuario que crea el módulo. |

## PUT /api/v1/modulos/\{item_id\}
Actualiza atributos de un módulo para ajustar presentación y orden funcional.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "3f8bd45e-aaea-4d53-be8e-c3ed303e4025"
  },
  "body": {
    "nombre": "Seguridad",
    "orden": 1,
    "icono": "lock",
    "usuario_auditoria": "admin"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "3f8bd45e-aaea-4d53-be8e-c3ed303e4025",
  "codigo": "SEGURIDAD",
  "nombre": "Seguridad",
  "descripcion": "Gestión de usuarios, roles y permisos",
  "orden": 1,
  "icono": "lock",
  "activo": true,
  "creado_en": "2026-02-23T08:50:00Z",
  "actualizado_en": "2026-02-23T09:10:00Z",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Módulo 3f8bd45e-aaea-4d53-be8e-c3ed303e4025 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Módulo objetivo de actualización. |
| codigo | string | No | Si se envía, mantiene unicidad y máximo 50 caracteres. |
| nombre | string | No | Si se envía, máximo 120 caracteres. |
| descripcion | string | No | Si se envía, máximo 255 caracteres. |
| orden | int | No | Orden para menú. |
| icono | string | No | Nombre de icono; máximo 50 caracteres. |
| usuario_auditoria | string | No | Usuario que realiza el cambio. |

## DELETE /api/v1/modulos/\{item_id\}
Desactiva un módulo para retirarlo del catálogo sin eliminar historial.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "3f8bd45e-aaea-4d53-be8e-c3ed303e4025"
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
  "detail": "Módulo 3f8bd45e-aaea-4d53-be8e-c3ed303e4025 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador del módulo a desactivar. |

---

## GET /api/v1/roles-modulos-permisos
Lista asignaciones de permisos por rol y módulo para auditoría de seguridad.

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
      "id": "7a4af128-8f56-4c44-ad3f-52e47e0834f0",
      "rol_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
      "modulo_id": "e3fd8028-9f47-4bc2-9e4c-e889b592ef8d",
      "puede_leer": true,
      "puede_crear": true,
      "puede_actualizar": true,
      "puede_eliminar": false,
      "activo": true,
      "creado_en": "2026-02-23T09:20:00Z",
      "actualizado_en": "2026-02-23T09:20:00Z",
      "usuario_auditoria": "admin"
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
| only_active | bool | No | Si es `true`, lista solo asignaciones activas. |

## GET /api/v1/roles-modulos-permisos/\{item_id\}
Obtiene una asignación específica de permisos para inspección y soporte de seguridad.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "7a4af128-8f56-4c44-ad3f-52e47e0834f0"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "7a4af128-8f56-4c44-ad3f-52e47e0834f0",
  "rol_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
  "modulo_id": "e3fd8028-9f47-4bc2-9e4c-e889b592ef8d",
  "puede_leer": true,
  "puede_crear": true,
  "puede_actualizar": true,
  "puede_eliminar": false,
  "activo": true,
  "creado_en": "2026-02-23T09:20:00Z",
  "actualizado_en": "2026-02-23T09:20:00Z",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Permiso 7a4af128-8f56-4c44-ad3f-52e47e0834f0 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador de la asignación de permisos. |

## POST /api/v1/roles-modulos-permisos
Crea la relación de permisos entre un rol y un módulo para controlar operaciones CRUD autorizadas.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "rol_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
  "modulo_id": "e3fd8028-9f47-4bc2-9e4c-e889b592ef8d",
  "puede_leer": true,
  "puede_crear": true,
  "puede_actualizar": true,
  "puede_eliminar": false,
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="response" label="Response 201">

```json
{
  "id": "7a4af128-8f56-4c44-ad3f-52e47e0834f0",
  "rol_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
  "modulo_id": "e3fd8028-9f47-4bc2-9e4c-e889b592ef8d",
  "puede_leer": true,
  "puede_crear": true,
  "puede_actualizar": true,
  "puede_eliminar": false,
  "activo": true,
  "creado_en": "2026-02-23T09:20:00Z",
  "actualizado_en": "2026-02-23T09:20:00Z",
  "usuario_auditoria": "admin"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Registro duplicado: se violó la restricción única 'uq_rol_modulo'."
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| rol_id | UUID | Sí | Rol al que se asignan permisos. |
| modulo_id | UUID | Sí | Módulo sobre el que aplica el permiso. |
| puede_leer | bool | No | Default `false`. Habilita acceso de lectura. |
| puede_crear | bool | No | Default `false`. Habilita operaciones de creación. |
| puede_actualizar | bool | No | Default `false`. Habilita operaciones de actualización. |
| puede_eliminar | bool | No | Default `false`. Habilita operaciones de eliminación. |
| usuario_auditoria | string | No | Usuario que crea la asignación. |

## PUT /api/v1/roles-modulos-permisos/\{item_id\}
Actualiza los flags de autorización para ajustar el alcance operativo de un rol en un módulo.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "7a4af128-8f56-4c44-ad3f-52e47e0834f0"
  },
  "body": {
    "puede_leer": true,
    "puede_crear": true,
    "puede_actualizar": false,
    "puede_eliminar": false,
    "usuario_auditoria": "seguridad"
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
{
  "id": "7a4af128-8f56-4c44-ad3f-52e47e0834f0",
  "rol_id": "7ebca6cc-5c68-4600-bf7f-0a64b482f6e8",
  "modulo_id": "e3fd8028-9f47-4bc2-9e4c-e889b592ef8d",
  "puede_leer": true,
  "puede_crear": true,
  "puede_actualizar": false,
  "puede_eliminar": false,
  "activo": true,
  "creado_en": "2026-02-23T09:20:00Z",
  "actualizado_en": "2026-02-23T09:50:00Z",
  "usuario_auditoria": "seguridad"
}
```

</TabItem>
<TabItem value="error" label="Error 400">

```json
{
  "detail": "Permiso 7a4af128-8f56-4c44-ad3f-52e47e0834f0 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Asignación de permisos a actualizar. |
| puede_leer | bool | No | Si se envía, redefine permiso de lectura. |
| puede_crear | bool | No | Si se envía, redefine permiso de creación. |
| puede_actualizar | bool | No | Si se envía, redefine permiso de actualización. |
| puede_eliminar | bool | No | Si se envía, redefine permiso de eliminación. |
| usuario_auditoria | string | No | Usuario que ejecuta el cambio. |

## DELETE /api/v1/roles-modulos-permisos/\{item_id\}
Desactiva una asignación de permisos para revocar acceso sin borrar el histórico de auditoría.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "path": {
    "item_id": "7a4af128-8f56-4c44-ad3f-52e47e0834f0"
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
  "detail": "Permiso 7a4af128-8f56-4c44-ad3f-52e47e0834f0 not found"
}
```

</TabItem>
</Tabs>

Diccionario de Datos

| Campo | Tipo | Obligatorio | Descripción y Restricciones |
|---|---|---|---|
| item_id | UUID | Sí | Identificador de la asignación a desactivar. |

---

## GET /api/v1/audit-logs
Consulta la bitácora transversal de auditoría para trazabilidad de cambios y eventos de seguridad.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "query": {
    "usuario_id": "admin",
    "fecha_desde": "2026-02-20T00:00:00Z",
    "fecha_hasta": "2026-02-24T23:59:59Z",
    "limit": 100,
    "offset": 0
  }
}
```

</TabItem>
<TabItem value="response" label="Response 200">

```json
[
  {
    "id": "4f2a1f08-8e11-4c84-9219-3d0f6aa4e91e",
    "tabla_afectada": "tbl_empresa",
    "registro_id": "3f4bbf20-0192-4cda-a9b9-f2f1615c9d90",
    "accion": "UPDATE_REGIMEN_MODO",
    "estado_anterior": {
      "regimen": "GENERAL",
      "modo_emision": "ELECTRONICO"
    },
    "estado_nuevo": {
      "regimen": "RIMPE_NEGOCIO_POPULAR",
      "modo_emision": "NOTA_VENTA_FISICA"
    },
    "usuario_id": "admin",
    "fecha": "2026-02-24T10:11:12Z"
  }
]
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
| usuario_id | string | No | Filtra por usuario responsable (`usuario_id`, `created_by`, `updated_by` o `usuario_auditoria`). |
| fecha_desde | datetime | No | Límite inferior del rango de auditoría (ISO 8601). |
| fecha_hasta | datetime | No | Límite superior del rango de auditoría (ISO 8601). |
| limit | int | No | Tamaño de página lógica. Default `100`, mínimo `1`, máximo `1000`. |
| offset | int | No | Desplazamiento de resultados. Default `0`, mínimo `0`. |

---

## Matriz de Errores por Endpoint

| Endpoint | Códigos esperados |
|---|---|
| `GET /api/v1/usuarios` | `200`, `422` |
| `GET /api/v1/usuarios/{item_id}` | `200`, `404` |
| `POST /api/v1/usuarios` | `201`, `400`, `404`, `409`, `422` |
| `PUT /api/v1/usuarios/{item_id}` | `200`, `404`, `409`, `422` |
| `DELETE /api/v1/usuarios/{item_id}` | `204`, `404` |
| `GET /api/v1/usuarios/{usuario_id}/permisos` | `200`, `404`, `422` |
| `GET /api/v1/usuarios/{usuario_id}/menu` | `200`, `404`, `422` |
| `POST /api/v1/usuarios/{usuario_id}/reset-password` | `200`, `404`, `409`, `422` |
| `POST /api/v1/usuarios/{usuario_id}/verify-password` | `200`, `404`, `409`, `422` |
| `GET /api/v1/roles` | `200`, `422` |
| `GET /api/v1/roles/{item_id}` | `200`, `404` |
| `POST /api/v1/roles` | `201`, `409`, `422` |
| `PUT /api/v1/roles/{item_id}` | `200`, `404`, `409`, `422` |
| `DELETE /api/v1/roles/{item_id}` | `204`, `404` |
| `GET /api/v1/modulos` | `200`, `422` |
| `GET /api/v1/modulos/{item_id}` | `200`, `404` |
| `POST /api/v1/modulos` | `201`, `409`, `422` |
| `PUT /api/v1/modulos/{item_id}` | `200`, `404`, `409`, `422` |
| `DELETE /api/v1/modulos/{item_id}` | `204`, `404` |
| `GET /api/v1/roles-modulos-permisos` | `200`, `422` |
| `GET /api/v1/roles-modulos-permisos/{item_id}` | `200`, `404` |
| `POST /api/v1/roles-modulos-permisos` | `201`, `404`, `409`, `422` |
| `PUT /api/v1/roles-modulos-permisos/{item_id}` | `200`, `404`, `409`, `422` |
| `DELETE /api/v1/roles-modulos-permisos/{item_id}` | `204`, `404` |
| `GET /api/v1/audit-logs` | `200`, `422` |
