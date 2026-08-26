---
id: directorio
title: "Directorio: Personas y Entidades Comerciales"
sidebar_position: 3
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# Directorio: Personas y Entidades Comerciales

El módulo **Directorio** gestiona el registro centralizado de personas naturales, sus asociaciones comerciales como clientes y proveedores, así como la vinculación de empleados a la empresa. Este módulo es fundamental para mantener la base de datos de actores en el sistema (personas, clientes, proveedores y empleados).

## Política de Registros Activos (Frontend)

- El frontend debe usar por defecto `only_active=true` para mostrar registros vigentes.
- Los registros inactivos corresponden a **borrado lógico** y deben verse solo en vistas administrativas.
- `only_active=false` retorna registros inactivos.

## Estructura General

El Directorio está compuesto por 6 entidades principales:

1. **Persona** - Registro central de personas naturales con validaciones SRI Ecuador.
2. **Cliente** - Asociación entre una Persona y un Tipo de Cliente.
3. **Tipo de Cliente** - Catálogo de categorías de cliente con descuentos.
4. **Proveedor Persona** - Registro de proveedores que son personas naturales.
5. **Proveedor Sociedad** - Registro de proveedores que son empresas.
6. **Empleado** - Vinculación de personas como empleados de una sucursal.

---

## 1. Persona

### Descripción

Tabla central de personas naturales con validación integrada de documentos de identificación según el SRI Ecuador:
- **Cédula (10 dígitos)**: Identidad personal ecuatoriana.
- **RUC (13 dígitos)**: Registro Único de Contribuyente. Para personas naturales el RUC contiene los 10 dígitos de la cédula más 3 dígitos de secuencia.
- **Pasaporte**: Documento internacional (mínimo 5 caracteres).

### Endpoints

<Tabs>
  <TabItem value="get-list" label="Listar Personas" default>

**GET** `/api/v1/personas`

Obtiene una lista paginada de personas activas (por defecto) o todas.

**Parámetros de Query:**
- `limit` (int, default: 50) - Registros por página (min: 1, max: 1000)
- `offset` (int, default: 0) - Desplazamiento desde el inicio
- `only_active` (bool, default: true) - Si es `true`, solo personas activas

**Response 200:**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "identificacion": "1234567890",
      "tipo_identificacion": "CEDULA",
      "nombre": "Juan",
      "apellido": "Pérez López",
      "direccion": "Calle Principal 123, Quito",
      "telefono": "+593 98 123 4567",
      "ciudad": "Quito",
      "email": "juan.perez@ejemplo.com",
      "activo": true,
      "creado_en": "2024-01-15T10:30:00Z",
      "actualizado_en": "2024-01-15T10:30:00Z",
      "usuario_auditoria": "admin"
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

  <TabItem value="get-detail" label="Obtener Persona">

**GET** `/api/v1/personas/{id}`

Obtiene los detalles de una persona específica.

**Parámetros de Path:**
- `id` (UUID) - ID de la persona

**Response 200:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "identificacion": "1234567890",
  "tipo_identificacion": "CEDULA",
  "nombre": "Juan",
  "apellido": "Pérez López",
  "direccion": "Calle Principal 123, Quito",
  "telefono": "+593 98 123 4567",
  "ciudad": "Quito",
  "email": "juan.perez@ejemplo.com",
  "activo": true,
  "creado_en": "2024-01-15T10:30:00Z",
  "actualizado_en": "2024-01-15T10:30:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 404:**
```json
{
  "detail": "Persona 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

  </TabItem>

  <TabItem value="post" label="Crear Persona">

**POST** `/api/v1/personas`

Crea una nueva persona con validación automática de identificación según SRI Ecuador.

**Request Body:**
```json
{
  "identificacion": "1234567890",
  "tipo_identificacion": "CEDULA",
  "nombre": "Juan",
  "apellido": "Pérez López",
  "direccion": "Calle Principal 123, Quito",
  "telefono": "+593 98 123 4567",
  "ciudad": "Quito",
  "email": "juan.perez@ejemplo.com",
  "usuario_auditoria": "admin"
}
```

**Response 201:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "identificacion": "1234567890",
  "tipo_identificacion": "CEDULA",
  "nombre": "Juan",
  "apellido": "Pérez López",
  "direccion": "Calle Principal 123, Quito",
  "telefono": "+593 98 123 4567",
  "ciudad": "Quito",
  "email": "juan.perez@ejemplo.com",
  "activo": true,
  "creado_en": "2024-01-15T10:30:00Z",
  "actualizado_en": "2024-01-15T10:30:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 400 (Validación SRI fallida):**
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "identificacion"],
      "msg": "La cédula ingresada no es válida.",
      "input": "0000000000"
    }
  ]
}
```

  </TabItem>

  <TabItem value="put" label="Actualizar Persona">

**PUT** `/api/v1/personas/{id}`

Actualiza parcialmente una persona. Si se cambia la identificación, must incluir el tipo de identificación.

**Parámetros de Path:**
- `id` (UUID) - ID de la persona

**Request Body:**
```json
{
  "nombre": "Juan Carlos",
  "apellido": "Pérez Rodríguez",
  "email": "juan.carlos@ejemplo.com",
  "usuario_auditoria": "admin"
}
```

**Response 200:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "identificacion": "1234567890",
  "tipo_identificacion": "CEDULA",
  "nombre": "Juan Carlos",
  "apellido": "Pérez Rodríguez",
  "direccion": "Calle Principal 123, Quito",
  "telefono": "+593 98 123 4567",
  "ciudad": "Quito",
  "email": "juan.carlos@ejemplo.com",
  "activo": true,
  "creado_en": "2024-01-15T10:30:00Z",
  "actualizado_en": "2024-01-16T14:20:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 404:**
```json
{
  "detail": "Persona 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

  </TabItem>

  <TabItem value="delete" label="Eliminar Persona">

**DELETE** `/api/v1/personas/{id}`

Realiza un borrado lógico (soft delete) marcando la persona como inactiva.

**Parámetros de Path:**
- `id` (UUID) - ID de la persona

**Response 204:** No content

**Response 404:**
```json
{
  "detail": "Persona 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo | Tipo | Restricción | Descripción |
|-------|------|-----------|-------------|
| `id` | UUID | PK, Auto | Identificador único de la persona |
| `identificacion` | String(50) | Unique, Not Null | Documento de identidad. **Validación SRI**: Si `tipo_identificacion=CEDULA`, debe ser 10 dígitos válidos según algoritmo SRI. Si `RUC` (persona natural), debe ser 13 dígitos donde los primeros 10 son la cédula + 3 dígitos. |
| `tipo_identificacion` | Enum | Not Null | Tipo: `CEDULA` (10 dígitos), `RUC` (13 dígitos persona natural), `PASAPORTE` (mín. 5 caracteres) |
| `nombre` | String(120) | Not Null | Nombre de la persona |
| `apellido` | String(120) | Not Null | Apellido de la persona |
| `direccion` | String(255) | Optional | Domicilio |
| `telefono` | String(30) | Optional | Número de contacto |
| `ciudad` | String(120) | Optional | Ciudad de residencia |
| `email` | Email | Optional | Correo electrónico (formato válido) |
| `activo` | Boolean | Default: true | Indicador de estado (soft delete) |
| `creado_en` | DateTime | Auto | Timestamp de creación |
| `actualizado_en` | DateTime | Auto | Timestamp de última actualización |
| `usuario_auditoria` | String | Not Null | Usuario que realizó la acción |

---

## 2. Tipo de Cliente

### Descripción

Catálogo de tipos/categorías de cliente. Cada tipo define un descuento base que se aplica a los clientes de esa categoría.

### Endpoints

<Tabs>
  <TabItem value="get-list" label="Listar Tipos de Cliente" default>

**GET** `/api/v1/tipos-cliente`

Obtiene una lista paginada de tipos de cliente.

**Parámetros de Query:**
- `limit` (int, default: 50) - Registros por página
- `offset` (int, default: 0) - Desplazamiento
- `only_active` (bool, default: true) - Solo activos

**Response 200:**
```json
{
  "items": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "nombre": "Cliente Mayorista",
      "descuento": 15.50,
      "activo": true,
      "creado_en": "2024-01-10T09:00:00Z",
      "actualizado_en": "2024-01-10T09:00:00Z",
      "usuario_auditoria": "admin"
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "nombre": "Cliente Minorista",
      "descuento": 5.00,
      "activo": true,
      "creado_en": "2024-01-10T09:05:00Z",
      "actualizado_en": "2024-01-10T09:05:00Z",
      "usuario_auditoria": "admin"
    }
  ],
  "meta": {
    "total": 2,
    "limit": 50,
    "offset": 0
  }
}
```

  </TabItem>

  <TabItem value="get-detail" label="Obtener Tipo de Cliente">

**GET** `/api/v1/tipos-cliente/{id}`

Obtiene los detalles de un tipo de cliente específico.

**Response 200:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "nombre": "Cliente Mayorista",
  "descuento": 15.50,
  "activo": true,
  "creado_en": "2024-01-10T09:00:00Z",
  "actualizado_en": "2024-01-10T09:00:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="post" label="Crear Tipo de Cliente">

**POST** `/api/v1/tipos-cliente`

Crea una nueva categoría de cliente.

**Request Body:**
```json
{
  "nombre": "Cliente Especial",
  "descuento": 20.00,
  "usuario_auditoria": "admin"
}
```

**Response 201:**
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440000",
  "nombre": "Cliente Especial",
  "descuento": 20.00,
  "activo": true,
  "creado_en": "2024-01-16T11:45:00Z",
  "actualizado_en": "2024-01-16T11:45:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 400 (Descuento fuera de rango):**
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "descuento"],
      "msg": "Input should be less than or equal to 100",
      "input": 150.00
    }
  ]
}
```

  </TabItem>

  <TabItem value="put" label="Actualizar Tipo de Cliente">

**PUT** `/api/v1/tipos-cliente/{id}`

Actualiza parcialmente un tipo de cliente.

**Request Body:**
```json
{
  "descuento": 18.00,
  "usuario_auditoria": "admin"
}
```

**Response 200:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "nombre": "Cliente Mayorista",
  "descuento": 18.00,
  "activo": true,
  "creado_en": "2024-01-10T09:00:00Z",
  "actualizado_en": "2024-01-16T12:00:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="delete" label="Eliminar Tipo de Cliente">

**DELETE** `/api/v1/tipos-cliente/{id}`

Realiza un borrado lógico del tipo de cliente.

**Response 204:** No content

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo | Tipo | Restricción | Descripción |
|-------|------|-----------|-------------|
| `id` | UUID | PK, Auto | Identificador único |
| `nombre` | String(255) | Unique, Not Null | Nombre de la categoría (ej: "Mayorista", "Minorista", "Especial") |
| `descuento` | Decimal(5,2) | Default: 0, Range: [0-100] | Porcentaje de descuento base aplicable a este tipo de cliente |
| `activo` | Boolean | Default: true | Indicador de estado |
| `creado_en` | DateTime | Auto | Timestamp de creación |
| `actualizado_en` | DateTime | Auto | Timestamp de última actualización |
| `usuario_auditoria` | String | Not Null | Usuario auditor |

---

## 3. Cliente

### Descripción

Asociación entre una Persona y un Tipo de Cliente. Permite vincular personas naturales como clientes del sistema con una clasificación específica.

### Endpoints

<Tabs>
  <TabItem value="get-list" label="Listar Clientes" default>

**GET** `/api/v1/clientes`

Obtiene una lista paginada de clientes.

**Parámetros de Query:**
- `limit` (int, default: 50)
- `offset` (int, default: 0)
- `only_active` (bool, default: true)

**Response 200:**
```json
{
  "items": [
    {
      "id": "990e8400-e29b-41d4-a716-446655440000",
      "persona_id": "550e8400-e29b-41d4-a716-446655440000",
      "tipo_cliente_id": "660e8400-e29b-41d4-a716-446655440000",
      "activo": true,
      "creado_en": "2024-01-15T10:35:00Z",
      "actualizado_en": "2024-01-15T10:35:00Z",
      "usuario_auditoria": "admin"
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

  <TabItem value="get-detail" label="Obtener Cliente">

**GET** `/api/v1/clientes/{id}`

Obtiene los detalles de un cliente específico.

**Response 200:**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "tipo_cliente_id": "660e8400-e29b-41d4-a716-446655440000",
  "activo": true,
  "creado_en": "2024-01-15T10:35:00Z",
  "actualizado_en": "2024-01-15T10:35:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="post" label="Crear Cliente">

**POST** `/api/v1/clientes`

Crea una asociación entre una Persona y un Tipo de Cliente.

**Request Body:**
```json
{
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "tipo_cliente_id": "660e8400-e29b-41d4-a716-446655440000",
  "usuario_auditoria": "admin"
}
```

**Response 201:**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "tipo_cliente_id": "660e8400-e29b-41d4-a716-446655440000",
  "activo": true,
  "creado_en": "2024-01-15T10:35:00Z",
  "actualizado_en": "2024-01-15T10:35:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 409 (FK violada - persona_id no existe):**
```json
{
  "detail": "Foreign key violation: persona_id does not exist in tbl_persona"
}
```

  </TabItem>

  <TabItem value="put" label="Actualizar Cliente">

**PUT** `/api/v1/clientes/{id}`

Actualiza el tipo de cliente asociado. No se puede cambiar la persona.

**Request Body:**
```json
{
  "tipo_cliente_id": "770e8400-e29b-41d4-a716-446655440000",
  "usuario_auditoria": "admin"
}
```

**Response 200:**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "tipo_cliente_id": "770e8400-e29b-41d4-a716-446655440000",
  "activo": true,
  "creado_en": "2024-01-15T10:35:00Z",
  "actualizado_en": "2024-01-16T14:30:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="delete" label="Eliminar Cliente">

**DELETE** `/api/v1/clientes/{id}`

Realiza un borrado lógico del cliente.

**Response 204:** No content

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo | Tipo | Restricción | Descripción |
|-------|------|-----------|-------------|
| `id` | UUID | PK, Auto | Identificador único del cliente |
| `persona_id` | UUID | FK (tbl_persona.id), Unique, Not Null | Referencia a la persona vinculada como cliente. **Restricción**: Cada persona solo puede ser cliente una vez. |
| `tipo_cliente_id` | UUID | FK (tbl_tipo_cliente.id), Not Null | Referencia a la categoría de cliente |
| `activo` | Boolean | Default: true | Indicador de estado |
| `creado_en` | DateTime | Auto | Timestamp de creación |
| `actualizado_en` | DateTime | Auto | Timestamp de última actualización |
| `usuario_auditoria` | String | Optional | Usuario auditor |

---

## 4. Proveedor Persona

### Descripción

Registro de proveedores que son personas naturales. Debe estar vinculado a una Persona y contiene información comercial específica del proveedor.

Reglas de negocio backend (importantes para frontend):
- `persona_id` debe apuntar a una Persona con `tipo_identificacion = RUC`.
- El RUC de la persona debe ser de persona natural válido (no sociedad).
- `tipo_contribuyente_id` no puede corresponder a categorías de sociedad o gran contribuyente.
- En `PUT`, `persona_id` es inmutable y cualquier valor enviado se ignora.

### Endpoints

<Tabs>
  <TabItem value="get-list" label="Listar Proveedores Persona" default>

**GET** `/api/v1/proveedores-persona`

Obtiene una lista paginada de proveedores persona.

**Parámetros de Query:**
- `limit` (int, default: 50)
- `offset` (int, default: 0)
- `only_active` (bool, default: true)

**Response 200:**
```json
{
  "items": [
    {
      "id": "aaa0e8400-e29b-41d4-a716-446655440000",
      "nombre_comercial": "Distribuidora Pérez y Cía",
      "tipo_contribuyente_id": "01",
      "persona_id": "550e8400-e29b-41d4-a716-446655440000",
      "activo": true,
      "creado_en": "2024-01-15T11:00:00Z",
      "actualizado_en": "2024-01-15T11:00:00Z",
      "usuario_auditoria": "admin"
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

  <TabItem value="get-detail" label="Obtener Proveedor Persona">

**GET** `/api/v1/proveedores-persona/{id}`

Obtiene los detalles de un proveedor persona específico.

**Response 200:**
```json
{
  "id": "aaa0e8400-e29b-41d4-a716-446655440000",
  "nombre_comercial": "Distribuidora Pérez y Cía",
  "tipo_contribuyente_id": "01",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "activo": true,
  "creado_en": "2024-01-15T11:00:00Z",
  "actualizado_en": "2024-01-15T11:00:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="post" label="Crear Proveedor Persona">

**POST** `/api/v1/proveedores-persona`

Crea un nuevo proveedor persona.

**Request Body:**
```json
{
  "nombre_comercial": "Distribuidora Pérez y Cía",
  "tipo_contribuyente_id": "01",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "usuario_auditoria": "admin"
}
```

**Response 201:**
```json
{
  "id": "aaa0e8400-e29b-41d4-a716-446655440000",
  "nombre_comercial": "Distribuidora Pérez y Cía",
  "tipo_contribuyente_id": "01",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "activo": true,
  "creado_en": "2024-01-15T11:00:00Z",
  "actualizado_en": "2024-01-15T11:00:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="put" label="Actualizar Proveedor Persona">

**PUT** `/api/v1/proveedores-persona/{id}`

Actualiza un proveedor persona. No se puede cambiar la persona_id.

**Request Body:**
```json
{
  "nombre_comercial": "Distribuidora Pérez, López y Asociados",
  "usuario_auditoria": "admin"
}
```

**Response 200:**
```json
{
  "id": "aaa0e8400-e29b-41d4-a716-446655440000",
  "nombre_comercial": "Distribuidora Pérez, López y Asociados",
  "tipo_contribuyente_id": "01",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "activo": true,
  "creado_en": "2024-01-15T11:00:00Z",
  "actualizado_en": "2024-01-16T15:00:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="delete" label="Eliminar Proveedor Persona">

**DELETE** `/api/v1/proveedores-persona/{id}`

Realiza un borrado lógico del proveedor persona.

**Response 204:** No content

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo | Tipo | Restricción | Descripción |
|-------|------|-----------|-------------|
| `id` | UUID | PK, Auto | Identificador único |
| `nombre_comercial` | String(255) | Optional | Nombre bajo el cual opera comercialmente el proveedor |
| `tipo_contribuyente_id` | String(2) | FK (aux_tipo_contribuyente.codigo), Not Null | Clasificación SRI del contribuyente (ej: "01" = Persona Natural, "02" = Empresa) |
| `persona_id` | UUID | FK (tbl_persona.id), Not Null | Referencia a la Persona vinculada como proveedor |
| `activo` | Boolean | Default: true | Indicador de estado |
| `creado_en` | DateTime | Auto | Timestamp de creación |
| `actualizado_en` | DateTime | Auto | Timestamp de última actualización |
| `usuario_auditoria` | String | Not Null | Usuario auditor |

---

## 5. Proveedor Sociedad

### Descripción

Registro de proveedores que son empresas (sociedades). Contiene información detallada de la empresa y requiere un RUC válido de 13 dígitos.

Reglas de negocio backend (importantes para frontend):
- El `ruc` debe ser válido y no puede ser RUC de persona natural.
- `tipo_contribuyente_id` no admite códigos `01` ni `03`.
- `telefono`, si se envía, debe tener exactamente 10 dígitos numéricos.
- `email` debe cumplir formato válido.
- En `PUT`, `persona_contacto_id` es inmutable y cualquier valor enviado se ignora.

### Endpoints

<Tabs>
  <TabItem value="get-list" label="Listar Proveedores Sociedad" default>

**GET** `/api/v1/proveedores-sociedad`

Obtiene una lista paginada de proveedores sociedad.

**Parámetros de Query:**
- `limit` (int, default: 50)
- `offset` (int, default: 0)
- `only_active` (bool, default: true)

**Response 200:**
```json
{
  "items": [
    {
      "id": "bbb0e8400-e29b-41d4-a716-446655440000",
      "ruc": "1234567890001",
      "razon_social": "Distribuidora Nacional S.A.",
      "nombre_comercial": "DistNac",
      "direccion": "Avenida Colón 501, Quito",
      "telefono": "0222222222",
      "email": "ventas@distnac.com",
      "tipo_contribuyente_id": "02",
      "persona_contacto_id": "550e8400-e29b-41d4-a716-446655440000",
      "usuario_auditoria": "admin",
      "activo": true,
      "creado_en": "2024-01-15T12:00:00Z",
      "actualizado_en": "2024-01-15T12:00:00Z"
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

  <TabItem value="get-detail" label="Obtener Proveedor Sociedad">

**GET** `/api/v1/proveedores-sociedad/{id}`

Obtiene los detalles de un proveedor sociedad específico.

**Response 200:**
```json
{
  "id": "bbb0e8400-e29b-41d4-a716-446655440000",
  "ruc": "1234567890001",
  "razon_social": "Distribuidora Nacional S.A.",
  "nombre_comercial": "DistNac",
  "direccion": "Avenida Colón 501, Quito",
  "telefono": "0222222222",
  "email": "ventas@distnac.com",
  "tipo_contribuyente_id": "02",
  "persona_contacto_id": "550e8400-e29b-41d4-a716-446655440000",
  "usuario_auditoria": "admin",
  "activo": true,
  "creado_en": "2024-01-15T12:00:00Z",
  "actualizado_en": "2024-01-15T12:00:00Z"
}
```

  </TabItem>

  <TabItem value="post" label="Crear Proveedor Sociedad">

**POST** `/api/v1/proveedores-sociedad`

Crea un nuevo proveedor sociedad. El RUC debe ser exactamente 13 dígitos.

**Request Body:**
```json
{
  "ruc": "1234567890001",
  "razon_social": "Distribuidora Nacional S.A.",
  "nombre_comercial": "DistNac",
  "direccion": "Avenida Colón 501, Quito",
  "telefono": "0222222222",
  "email": "ventas@distnac.com",
  "tipo_contribuyente_id": "02",
  "persona_contacto_id": "550e8400-e29b-41d4-a716-446655440000",
  "usuario_auditoria": "admin"
}
```

**Response 201:**
```json
{
  "id": "bbb0e8400-e29b-41d4-a716-446655440000",
  "ruc": "1234567890001",
  "razon_social": "Distribuidora Nacional S.A.",
  "nombre_comercial": "DistNac",
  "direccion": "Avenida Colón 501, Quito",
  "telefono": "0222222222",
  "email": "ventas@distnac.com",
  "tipo_contribuyente_id": "02",
  "persona_contacto_id": "550e8400-e29b-41d4-a716-446655440000",
  "usuario_auditoria": "admin",
  "activo": true,
  "creado_en": "2024-01-15T12:00:00Z",
  "actualizado_en": "2024-01-15T12:00:00Z"
}
```

**Response 400 (RUC inválido):**
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "ruc"],
      "msg": "El RUC debe tener 13 dígitos",
      "input": "123456789"
    }
  ]
}
```

  </TabItem>

  <TabItem value="put" label="Actualizar Proveedor Sociedad">

**PUT** `/api/v1/proveedores-sociedad/{id}`

Actualiza un proveedor sociedad. No se puede cambiar persona_contacto_id.

**Request Body:**
```json
{
  "razon_social": "Distribuidora Nacional de Productos S.A.",
  "nombre_comercial": "DistNac Premium",
  "usuario_auditoria": "admin"
}
```

**Response 200:**
```json
{
  "id": "bbb0e8400-e29b-41d4-a716-446655440000",
  "ruc": "1234567890001",
  "razon_social": "Distribuidora Nacional de Productos S.A.",
  "nombre_comercial": "DistNac Premium",
  "direccion": "Avenida Colón 501, Quito",
  "telefono": "+593 2 2222222",
  "email": "ventas@distnac.com",
  "tipo_contribuyente_id": "02",
  "persona_contacto_id": "550e8400-e29b-41d4-a716-446655440000",
  "usuario_auditoria": "admin",
  "activo": true,
  "creado_en": "2024-01-15T12:00:00Z",
  "actualizado_en": "2024-01-16T16:00:00Z"
}
```

  </TabItem>

  <TabItem value="delete" label="Eliminar Proveedor Sociedad">

**DELETE** `/api/v1/proveedores-sociedad/{id}`

Realiza un borrado lógico del proveedor sociedad.

**Response 204:** No content

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo | Tipo | Restricción | Descripción |
|-------|------|-----------|-------------|
| `id` | UUID | PK, Auto | Identificador único |
| `ruc` | String(13) | Unique, Not Null, Exactly 13 | RUC de la empresa según SRI Ecuador (13 dígitos exactos). Formato: 10 primeros dígitos + 3 dígitos de secuencia. |
| `razon_social` | String(255) | Not Null | Nombre legal de la empresa registrado en SRI |
| `nombre_comercial` | String(255) | Optional | Nombre comercial bajo el que opera |
| `direccion` | String(255) | Not Null | Domicilio principal de la empresa |
| `telefono` | String | Optional | Si se envía, debe tener exactamente 10 dígitos numéricos. |
| `email` | Email | Not Null | Correo electrónico principal (formato válido) |
| `tipo_contribuyente_id` | String(2) | FK (aux_tipo_contribuyente.codigo), Not Null | Clasificación SRI. Restricción de negocio: no se permite `01` ni `03` para proveedor sociedad. |
| `persona_contacto_id` | UUID | FK (tbl_persona.id), Not Null | Referencia a una Persona como contacto. **Restricción**: No se puede cambiar en actualización. |
| `activo` | Boolean | Default: true | Indicador de estado |
| `creado_en` | DateTime | Auto | Timestamp de creación |
| `actualizado_en` | DateTime | Auto | Timestamp de última actualización |
| `usuario_auditoria` | String | Not Null | Usuario auditor |

---

## 6. Empleado

### Descripción

Vinculación de una Persona como Empleado de una Empresa. Incluye información laboral (salario, fechas) y puede crear automáticamente un Usuario asociado al empleado.

Reglas de negocio backend (importantes para frontend):
- `POST /empleados` exige el bloque `usuario` para crear la cuenta en la misma transacción.
- `fecha_ingreso` no puede ser futura.
- `fecha_salida`, cuando existe, debe ser posterior a `fecha_ingreso`.
- `fecha_nacimiento`, cuando existe, debe respetar edad mínima (`EMP_MIN_AGE`, default `16`).

### Endpoints

<Tabs>
  <TabItem value="get-list" label="Listar Empleados" default>

**GET** `/api/v1/empleados`

Obtiene una lista paginada de empleados.

**Parámetros de Query:**
- `limit` (int, default: 50)
- `offset` (int, default: 0)
- `only_active` (bool, default: true)

**Response 200:**
```json
{
  "items": [
    {
      "id": "ccc0e8400-e29b-41d4-a716-446655440000",
      "persona_id": "550e8400-e29b-41d4-a716-446655440000",
      "empresa_id": "ddd0e8400-e29b-41d4-a716-446655440000",
      "salario": 1500.00,
      "fecha_ingreso": "2024-01-01",
      "fecha_nacimiento": "1990-06-15",
      "fecha_salida": null,
      "foto": "https://storage.example.com/empleados/juan_perez.jpg",
      "activo": true,
      "creado_en": "2024-01-15T13:30:00Z",
      "actualizado_en": "2024-01-15T13:30:00Z",
      "usuario_auditoria": "admin"
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

  <TabItem value="get-detail" label="Obtener Empleado">

**GET** `/api/v1/empleados/{id}`

Obtiene los detalles de un empleado específico.

**Response 200:**
```json
{
  "id": "ccc0e8400-e29b-41d4-a716-446655440000",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "empresa_id": "ddd0e8400-e29b-41d4-a716-446655440000",
  "salario": 1500.00,
  "fecha_ingreso": "2024-01-01",
  "fecha_nacimiento": "1990-06-15",
  "fecha_salida": null,
  "foto": "https://storage.example.com/empleados/juan_perez.jpg",
  "activo": true,
  "creado_en": "2024-01-15T13:30:00Z",
  "actualizado_en": "2024-01-15T13:30:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="post" label="Crear Empleado">

**POST** `/api/v1/empleados`

Crea un nuevo empleado e inmediatamente genera un usuario asociado. Define validaciones por edad mínima y secuencia de fechas.

**Request Body:**
```json
{
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "empresa_id": "ddd0e8400-e29b-41d4-a716-446655440000",
  "salario": 1500.00,
  "fecha_ingreso": "2024-01-01",
  "fecha_nacimiento": "1990-06-15",
  "foto": "https://storage.example.com/empleados/juan_perez.jpg",
  "usuario": {
    "username": "jperez",
    "password": "MiContraseñaSegura123!",
    "rol_id": "eee0e8400-e29b-41d4-a716-446655440000",
    "usuario_auditoria": "admin"
  },
  "usuario_auditoria": "admin"
}
```

**Response 201:**
```json
{
  "id": "ccc0e8400-e29b-41d4-a716-446655440000",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "empresa_id": "ddd0e8400-e29b-41d4-a716-446655440000",
  "salario": 1500.00,
  "fecha_ingreso": "2024-01-01",
  "fecha_nacimiento": "1990-06-15",
  "fecha_salida": null,
  "foto": "https://storage.example.com/empleados/juan_perez.jpg",
  "activo": true,
  "creado_en": "2024-01-15T13:30:00Z",
  "actualizado_en": "2024-01-15T13:30:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 400 (Edad mínima no cumplida, default EMP_MIN_AGE=16):**
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "El empleado debe tener al menos 16 años.",
      "input": { "fecha_nacimiento": "2020-01-01" }
    }
  ]
}
```

**Response 400 (Fecha de salida anterior a ingreso):**
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "La fecha de salida debe ser posterior a la fecha de ingreso.",
      "input": { "fecha_ingreso": "2024-01-01", "fecha_salida": "2023-12-31" }
    }
  ]
}
```

  </TabItem>

  <TabItem value="put" label="Actualizar Empleado">

**PUT** `/api/v1/empleados/{id}`

Actualiza parcialmente un empleado. No se puede cambiar persona_id.

**Request Body:**
```json
{
  "salario": 1800.00,
  "fecha_salida": "2024-12-31",
  "usuario_auditoria": "admin"
}
```

**Response 200:**
```json
{
  "id": "ccc0e8400-e29b-41d4-a716-446655440000",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "empresa_id": "ddd0e8400-e29b-41d4-a716-446655440000",
  "salario": 1800.00,
  "fecha_ingreso": "2024-01-01",
  "fecha_nacimiento": "1990-06-15",
  "fecha_salida": "2024-12-31",
  "foto": "https://storage.example.com/empleados/juan_perez.jpg",
  "activo": true,
  "creado_en": "2024-01-15T13:30:00Z",
  "actualizado_en": "2024-01-20T10:00:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="delete" label="Eliminar Empleado">

**DELETE** `/api/v1/empleados/{id}`

Realiza un borrado lógico del empleado.

**Response 204:** No content

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo | Tipo | Restricción | Descripción |
|-------|------|-----------|-------------|
| `id` | UUID | PK, Auto | Identificador único |
| `persona_id` | UUID | FK (tbl_persona.id), Unique, Not Null | Referencia a la Persona vinculada. Cada persona solo puede ser empleado una vez. |
| `empresa_id` | UUID | FK (tbl_empresa.id), Not Null | Referencia a la Empresa que lo emplea |
| `salario` | Decimal(10,2) | Not Null | Salario mensual en USD |
| `fecha_ingreso` | Date | Not Null | Fecha de inicio laboral. No puede ser futura. |
| `fecha_nacimiento` | Date | Optional | Fecha de nacimiento. Si se proporciona, se valida **edad mínima** (default EMP_MIN_AGE=16, configurable por env var). |
| `fecha_salida` | Date | Optional | Fecha de cese laboral. Si está presente, debe ser posterior a fecha_ingreso. |
| `foto` | String(500) | Optional | URL o ruta a foto del empleado |
| `activo` | Boolean | Default: true | Indicador de estado |
| `creado_en` | DateTime | Auto | Timestamp de creación |
| `actualizado_en` | DateTime | Auto | Timestamp de última actualización |
| `usuario_auditoria` | String | Optional | Usuario auditor |

---

## Validaciones SRI Ecuador - Resumen

### Persona: Tipos de Identificación

1. **CEDULA** (10 dígitos)
   - Identificación personal única emitida por el SRI
   - Algoritmo de validación: módulo 11 aplicado a los 9 primeros dígitos
   - Ejemplo válido: `1234567890`

2. **RUC** (13 dígitos, para personas naturales)
   - Compuesto por: 10 primeros dígitos (cédula) + 3 dígitos de secuencia
   - Aplicable a personas naturales que son contribuyentes
   - Ejemplo válido: `1234567890001` (cédula + "001")

3. **PASAPORTE** (mín. 5 caracteres)
   - Documento internacional
   - Validación: mínimo 5 caracteres

### Proveedor Sociedad: RUC Empresas

- **RUC** (13 dígitos exactos)
- Aplicable a empresas/sociedades comerciales
- Formato: 10 primeros dígitos de cédula del representante + 3 dígitos de secuencia de empresa (generalmente 001)
- Ejemplo válido: `1234567890001`

### Tipo Contribuyente

Campo `tipo_contribuyente_id` (2 caracteres) clasifica según SRI:
- `"01"` - Persona Natural
- `"02"` - Empresa/Sociedad
- Otros códigos SRI según catálogo

---

## Notas de Implementación

### Soft Delete

Todas las entidades del módulo Directorio implementan **borrado lógico** (soft delete):
- Campo `activo: boolean` (default: `true`)
- DELETE endpoint realiza update a `activo=false`
- GET con parámetro `only_active=true` filtran automáticamente registros inactivos

### Auditoría

Todas las entidades registran:
- `creado_en`: Timestamp de creación (auto)
- `actualizado_en`: Timestamp de última actualización (auto)
- `usuario_auditoria`: Usuario que realizó la acción (campo requerido en POST/PUT)

### Relaciones Críticas

- **Cliente** requiere `persona_id` y `tipo_cliente_id` válidos
- **Proveedor Persona** requiere `persona_id` válido
- **Proveedor Sociedad** requiere `persona_contacto_id` válido
- **Empleado** requiere `persona_id` y `empresa_id` válidos, además crea un Usuario automáticamente

### Restricciones Únicas

- Una Persona solo puede ser **Cliente** una vez
- Una Persona solo puede ser **Empleado** una vez
- Una Persona puede ser **Proveedor Persona** una sola vez
- `tipo_cliente.nombre` debe ser único
- `proveedor_sociedad.ruc` debe ser único
- `persona.identificacion` debe ser único

---

## Matriz de Errores por Endpoint

| Endpoint | Códigos esperados |
|---|---|
| `GET /api/v1/personas` | `200`, `422` |
| `GET /api/v1/personas/{id}` | `200`, `404` |
| `POST /api/v1/personas` | `201`, `400`, `409`, `422` |
| `PUT /api/v1/personas/{id}` | `200`, `400`, `404`, `409`, `422` |
| `DELETE /api/v1/personas/{id}` | `204`, `404` |
| `GET /api/v1/tipos-cliente` | `200`, `422` |
| `GET /api/v1/tipos-cliente/{id}` | `200`, `404` |
| `POST /api/v1/tipos-cliente` | `201`, `409`, `422` |
| `PUT /api/v1/tipos-cliente/{id}` | `200`, `404`, `409`, `422` |
| `DELETE /api/v1/tipos-cliente/{id}` | `204`, `404` |
| `GET /api/v1/clientes` | `200`, `422` |
| `GET /api/v1/clientes/{id}` | `200`, `404` |
| `POST /api/v1/clientes` | `201`, `404`, `409`, `422` |
| `PUT /api/v1/clientes/{id}` | `200`, `404`, `409`, `422` |
| `DELETE /api/v1/clientes/{id}` | `204`, `404` |
| `GET /api/v1/proveedores-persona` | `200`, `422` |
| `GET /api/v1/proveedores-persona/{id}` | `200`, `404` |
| `POST /api/v1/proveedores-persona` | `201`, `400`, `404`, `409`, `422` |
| `PUT /api/v1/proveedores-persona/{id}` | `200`, `400`, `404`, `409`, `422` |
| `DELETE /api/v1/proveedores-persona/{id}` | `204`, `404` |
| `GET /api/v1/proveedores-sociedad` | `200`, `422` |
| `GET /api/v1/proveedores-sociedad/{id}` | `200`, `404` |
| `POST /api/v1/proveedores-sociedad` | `201`, `400`, `404`, `409`, `422` |
| `PUT /api/v1/proveedores-sociedad/{id}` | `200`, `400`, `404`, `409`, `422` |
| `DELETE /api/v1/proveedores-sociedad/{id}` | `204`, `404` |
| `GET /api/v1/empleados` | `200`, `422` |
| `GET /api/v1/empleados/{id}` | `200`, `404` |
| `POST /api/v1/empleados` | `201`, `400`, `404`, `409`, `422` |
| `PUT /api/v1/empleados/{id}` | `200`, `400`, `404`, `409`, `422` |
| `DELETE /api/v1/empleados/{id}` | `204`, `404` |
