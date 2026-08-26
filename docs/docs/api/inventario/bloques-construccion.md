---
id: bloques-construccion
title: "Bloques de Construcción: Categorías y Atributos"
sidebar_position: 1
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# Bloques de Construcción: Categorías y Atributos

El módulo **Bloques de Construcción** del Inventario define la estructura taxonomía de productos mediante jerarquías de categorías y asignación flexible de atributos. Este módulo es fundamental para clasificar y caracterizar productos de forma dinámica.

## Política de Registros Activos (Frontend)

- En listados, usar `only_active=true` como valor por defecto.
- Los registros inactivos son borrado lógico y deben usarse solo en mantenimiento/auditoría.
- Para formularios de creación/edición de producto, cargar únicamente categorías y atributos activos.

## Estructura General

Los Bloques de Construcción están compuestos por 3 entidades principales:

1. **Categoría** - Jerarquía árbol de categorías de productos con soporte para subcategorías.
2. **Atributo** - Características reutilizables (color, tamaño, material, etc.) con tipos de datos tipados.
3. **Categoría-Atributo** - Asignación flexible de atributos a categorías con valor por defecto y obligatoriedad.

---

## 1. Categoría

### Descripción

Tabla jerárquica de categorías de productos que permite estructurar el inventario en forma de árbol. Cada categoría puede ser madre (`es_padre=true`) o contener una referencia a su categoría padre (`parent_id`).

### Endpoints

<Tabs>
  <TabItem value="get-list" label="Listar Categorías" default>

**GET** `/api/v1/categorias`

Obtiene una lista paginada de categorías activas (por defecto) o todas.

**Parámetros de Query:**
- `limit` (int, default: 50) - Registros por página (min: 1, max: 1000)
- `offset` (int, default: 0) - Desplazamiento desde el inicio
- `only_active` (bool, default: true) - Si es `true`, solo categorías activas

**Response 200:**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "nombre": "Electrónica",
      "es_padre": true,
      "parent_id": null,
      "activo": true,
      "creado_en": "2024-01-15T10:30:00Z",
      "actualizado_en": "2024-01-15T10:30:00Z",
      "usuario_auditoria": "admin"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "nombre": "Computadoras",
      "es_padre": false,
      "parent_id": "550e8400-e29b-41d4-a716-446655440000",
      "activo": true,
      "creado_en": "2024-01-15T10:35:00Z",
      "actualizado_en": "2024-01-15T10:35:00Z",
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

  <TabItem value="get-detail" label="Obtener Categoría">

**GET** `/api/v1/categorias/{item_id}`

Obtiene los detalles de una categoría específica.

**Parámetros de Path:**
- `item_id` (UUID) - ID de la categoría

**Response 200:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "nombre": "Electrónica",
  "es_padre": true,
  "parent_id": null,
  "activo": true,
  "creado_en": "2024-01-15T10:30:00Z",
  "actualizado_en": "2024-01-15T10:30:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 404:**
```json
{
  "detail": "Categoría 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

  </TabItem>

  <TabItem value="post" label="Crear Categoría">

**POST** `/api/v1/categorias`

Crea una nueva categoría. Puede ser una categoría raíz (`parent_id=null`) o subcategoría de una categoría existente.

**Request Body:**
```json
{
  "nombre": "Computadoras",
  "es_padre": true,
  "parent_id": "550e8400-e29b-41d4-a716-446655440000",
  "usuario_auditoria": "admin"
}
```

**Response 201:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "nombre": "Computadoras",
  "es_padre": true,
  "parent_id": "550e8400-e29b-41d4-a716-446655440000",
  "activo": true,
  "creado_en": "2024-01-15T10:35:00Z",
  "actualizado_en": "2024-01-15T10:35:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 409 (FK violada):**
```json
{
  "detail": "Foreign key violation: parent_id does not exist in tbl_categoria"
}
```

  </TabItem>

  <TabItem value="put" label="Actualizar Categoría">

**PUT** `/api/v1/categorias/{item_id}`

Actualiza parcialmente una categoría. Permite cambiar nombre, es_padre, o parent_id.

**Parámetros de Path:**
- `item_id` (UUID) - ID de la categoría

**Request Body:**
```json
{
  "nombre": "Computadoras de Escritorio",
  "es_padre": false,
  "usuario_auditoria": "admin"
}
```

**Response 200:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "nombre": "Computadoras de Escritorio",
  "es_padre": false,
  "parent_id": "550e8400-e29b-41d4-a716-446655440000",
  "activo": true,
  "creado_en": "2024-01-15T10:35:00Z",
  "actualizado_en": "2024-01-16T14:20:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 404:**
```json
{
  "detail": "Categoría 660e8400-e29b-41d4-a716-446655440000 not found"
}
```

  </TabItem>

  <TabItem value="delete" label="Eliminar Categoría">

**DELETE** `/api/v1/categorias/{item_id}`

Realiza un borrado lógico (soft delete) marcando la categoría como inactiva.

**Parámetros de Path:**
- `id` (UUID) - ID de la categoría

**Response 204:** No content

**Response 404:**
```json
{
  "detail": "Categoría 660e8400-e29b-41d4-a716-446655440000 not found"
}
```

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo | Tipo | Restricción | Descripción |
|-------|------|-----------|-------------|
| `id` | UUID | PK, Auto | Identificador único de la categoría |
| `nombre` | String(255) | Not Null, Index | Nombre descriptivo de la categoría (ej: "Electrónica", "Computadoras", "Ropa") |
| `es_padre` | Boolean | Default: false, Not Null | Indicador de si esta categoría es padre de subcategorías. Facilita consultas jerárquicas. |
| `parent_id` | UUID | FK (tbl_categoria.id), Optional | Referencia a la categoría padre si es una subcategoría. Si es nula, es una categoría raíz. |
| `activo` | Boolean | Default: true | Indicador de estado (soft delete) |
| `creado_en` | DateTime | Auto | Timestamp de creación |
| `actualizado_en` | DateTime | Auto | Timestamp de última actualización |
| `usuario_auditoria` | String | Optional | Usuario que realizó la acción |

---

## 2. Atributo

### Descripción

Catálogo de atributos reutilizables que pueden ser asignados a múltiples categorías. Cada atributo tiene un tipo de dato definido que permite validar los valores asignados en productos.

**Tipos de Dato Soportados:**
- `string` - Texto libre (ej: "Rojo", "Algodón 100%")
- `integer` - Números enteros (ej: 42 horas de batería)
- `decimal` - Números decimales (ej: 2.5 kg)
- `boolean` - Valor booleano (ej: "Tiene garantía": true/false)
- `date` - Fecha ISO (ej: "2024-12-31")

### Endpoints

<Tabs>
  <TabItem value="get-list" label="Listar Atributos" default>

**GET** `/api/v1/atributos`

Obtiene una lista paginada de atributos activos.

**Parámetros de Query:**
- `limit` (int, default: 50)
- `offset` (int, default: 0)
- `only_active` (bool, default: true)

**Response 200:**
```json
{
  "items": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "nombre": "Color",
      "tipo_dato": "string",
      "activo": true,
      "creado_en": "2024-01-10T09:00:00Z",
      "actualizado_en": "2024-01-10T09:00:00Z",
      "usuario_auditoria": "admin"
    },
    {
      "id": "880e8400-e29b-41d4-a716-446655440000",
      "nombre": "Peso",
      "tipo_dato": "decimal",
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

  <TabItem value="get-detail" label="Obtener Atributo">

**GET** `/api/v1/atributos/{item_id}`

Obtiene los detalles de un atributo específico.

**Response 200:**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "nombre": "Color",
  "tipo_dato": "string",
  "activo": true,
  "creado_en": "2024-01-10T09:00:00Z",
  "actualizado_en": "2024-01-10T09:00:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="post" label="Crear Atributo">

**POST** `/api/v1/atributos`

Crea un nuevo atributo reutilizable. El nombre debe ser único.

**Request Body:**
```json
{
  "nombre": "Color",
  "tipo_dato": "string",
  "usuario_auditoria": "admin"
}
```

**Response 201:**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "nombre": "Color",
  "tipo_dato": "string",
  "activo": true,
  "creado_en": "2024-01-10T09:00:00Z",
  "actualizado_en": "2024-01-10T09:00:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 409 (Nombre duplicado):**
```json
{
  "detail": "Atributo con nombre 'Color' ya existe"
}
```

  </TabItem>

  <TabItem value="put" label="Actualizar Atributo">

**PUT** `/api/v1/atributos/{item_id}`

Actualiza un atributo. Se puede cambiar nombre y tipo_dato.

**Request Body:**
```json
{
  "nombre": "Colores Disponibles",
  "usuario_auditoria": "admin"
}
```

**Response 200:**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "nombre": "Colores Disponibles",
  "tipo_dato": "string",
  "activo": true,
  "creado_en": "2024-01-10T09:00:00Z",
  "actualizado_en": "2024-01-15T12:00:00Z",
  "usuario_auditoria": "admin"
}
```

  </TabItem>

  <TabItem value="delete" label="Eliminar Atributo">

**DELETE** `/api/v1/atributos/{item_id}`

Realiza un borrado lógico del atributo. Las asignaciones en `categoria_atributo` permanecen inactivas.

**Response 204:** No content

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo | Tipo | Restricción | Descripción |
|-------|------|-----------|-------------|
| `id` | UUID | PK, Auto | Identificador único del atributo |
| `nombre` | String(120) | Unique, Not Null, Index | Nombre único del atributo (ej: "Color", "Tamaño", "Material", "Peso", "Garantía") |
| `tipo_dato` | Enum | Not Null | Tipo de dato: `string`, `integer`, `decimal`, `boolean`, `date`. Define el formato esperado en valores. |
| `activo` | Boolean | Default: true | Indicador de estado |
| `creado_en` | DateTime | Auto | Timestamp de creación |
| `actualizado_en` | DateTime | Auto | Timestamp de última actualización |
| `usuario_auditoria` | String | Optional | Usuario auditor |

---

## 3. Categoría-Atributo

### Descripción

Tabla de asignación que vincula atributos a categorías, permitiendo caracterizar dinámicamente productos pertenecientes a esa categoría. Cada asignación puede definir:

- **orden**: Posición visual para mostrar atributos en formularios o listados
- **obligatorio**: Si el atributo debe tener un valor en todos los productos de la categoría
- **valor_default**: Valor por defecto que se asigna automáticamente si no se proporciona otro

### Cómo Funciona

**Flujo de Asignación:**

```
1. Se crea un Atributo (ej: "Color" de tipo string)
2. Se crea una Categoría (ej: "Camisetas")
3. Se asigna el Atributo a la Categoría vía CategoriaAtributo:
   - orden = 1
   - obligatorio = true
   - valor_default = "Negro"
4. Los productos de categoría "Camisetas" heredan este atributo
5. Si se crea un producto sin especificar "Color", toma "Negro"
```

### Endpoints

<Tabs>
  <TabItem value="get-list" label="Listar Asignaciones" default>

**GET** `/api/v1/categorias-atributos`

Obtiene una lista de asignaciones categoría-atributo con soporte para filtrar por categoría.

**Parámetros de Query:**
- `skip` (int, default: 0) - Desplazamiento
- `limit` (int, default: 50) - Registros por página (max: 200)
- `categoria_id` (UUID, optional) - Filtrar por categoría específica

**Response 200:**
```json
[
  {
    "id": "990e8400-e29b-41d4-a716-446655440000",
    "categoria_id": "660e8400-e29b-41d4-a716-446655440000",
    "atributo_id": "770e8400-e29b-41d4-a716-446655440000",
    "orden": 1,
    "obligatorio": true,
    "valor_default": "Negro",
    "usuario_auditoria": "admin",
    "activo": true,
    "creado_en": "2024-01-15T11:00:00Z",
    "actualizado_en": "2024-01-15T11:00:00Z"
  }
]
```

  </TabItem>

  <TabItem value="get-detail" label="Obtener Asignación">

**GET** `/api/v1/categorias-atributos/{id}`

Obtiene los detalles de una asignación categoría-atributo específica.

**Response 200:**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "categoria_id": "660e8400-e29b-41d4-a716-446655440000",
  "atributo_id": "770e8400-e29b-41d4-a716-446655440000",
  "orden": 1,
  "obligatorio": true,
  "valor_default": "Negro",
  "usuario_auditoria": "admin",
  "activo": true,
  "creado_en": "2024-01-15T11:00:00Z",
  "actualizado_en": "2024-01-15T11:00:00Z"
}
```

  </TabItem>

  <TabItem value="post" label="Asignar Atributo a Categoría">

**POST** `/api/v1/categorias-atributos`

Crea una asignación entre un atributo y una categoría.

**Request Body:**
```json
{
  "categoria_id": "660e8400-e29b-41d4-a716-446655440000",
  "atributo_id": "770e8400-e29b-41d4-a716-446655440000",
  "orden": 1,
  "obligatorio": true,
  "valor_default": "Negro",
  "usuario_auditoria": "admin"
}
```

**Response 201:**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "categoria_id": "660e8400-e29b-41d4-a716-446655440000",
  "atributo_id": "770e8400-e29b-41d4-a716-446655440000",
  "orden": 1,
  "obligatorio": true,
  "valor_default": "Negro",
  "usuario_auditoria": "admin",
  "activo": true,
  "creado_en": "2024-01-15T11:00:00Z",
  "actualizado_en": "2024-01-15T11:00:00Z"
}
```

**Response 400 (valor_default no cumple tipo_dato):**
```json
{
  "detail": [
    {
      "type": "value_error",
      "msg": "El valor_default 'abc' no es válido para tipo_dato 'integer'",
      "input": "abc"
    }
  ]
}
```

  </TabItem>

  <TabItem value="put" label="Actualizar Asignación">

**PUT** `/api/v1/categorias-atributos/{id}`

Actualiza los parámetros de una asignación (orden, obligatorio, valor_default).

**Request Body:**
```json
{
  "orden": 2,
  "obligatorio": false,
  "valor_default": "Gris",
  "usuario_auditoria": "admin"
}
```

**Response 200:**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "categoria_id": "660e8400-e29b-41d4-a716-446655440000",
  "atributo_id": "770e8400-e29b-41d4-a716-446655440000",
  "orden": 2,
  "obligatorio": false,
  "valor_default": "Gris",
  "usuario_auditoria": "admin",
  "activo": true,
  "creado_en": "2024-01-15T11:00:00Z",
  "actualizado_en": "2024-01-16T15:00:00Z"
}
```

  </TabItem>

  <TabItem value="delete" label="Desasignar Atributo">

**DELETE** `/api/v1/categorias-atributos/{id}`

Realiza un borrado lógico de la asignación categoría-atributo.

**Response 204:** No content

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo | Tipo | Restricción | Descripción |
|-------|------|-----------|-------------|
| `id` | UUID | PK, Auto | Identificador único de la asignación |
| `categoria_id` | UUID | FK (tbl_categoria.id), Not Null | Referencia a la categoría que recibe el atributo |
| `atributo_id` | UUID | FK (tbl_atributo.id), Not Null | Referencia al atributo asignado |
| `orden` | Integer | Optional | Número de orden para mostrar el atributo en formularios (ej: 1, 2, 3...). Facilita el ordenamiento visual. |
| `obligatorio` | Boolean | Optional | Si `true`, el atributo debe tener un valor en todo producto de esta categoría. Si `false` o nulo, es opcional. |
| `valor_default` | String | Optional | Valor por defecto que se asigna automáticamente si no se proporciona otro. **Validación**: Debe cumplir el `tipo_dato` del atributo (ej: si tipo_dato="integer", valor_default debe ser un número). |
| `usuario_auditoria` | String | Optional | Usuario que realizó la acción |
| `activo` | Boolean | Default: true | Indicador de estado |
| `creado_en` | DateTime | Auto | Timestamp de creación |
| `actualizado_en` | DateTime | Auto | Timestamp de última actualización |

---

## Ejemplos de Uso Integrado

### Caso 1: Categoría "Camisetas" con Atributos

**Paso 1: Crear Atributos**
```json
POST /api/v1/atributos
{
  "nombre": "Color",
  "tipo_dato": "string",
  "usuario_auditoria": "admin"
}

POST /api/v1/atributos
{
  "nombre": "Talla",
  "tipo_dato": "string",
  "usuario_auditoria": "admin"
}

POST /api/v1/atributos
{
  "nombre": "Material",
  "tipo_dato": "string",
  "usuario_auditoria": "admin"
}
```

**Paso 2: Crear Categoría**
```json
POST /api/v1/categorias
{
  "nombre": "Camisetas",
  "es_padre": false,
  "parent_id": null,
  "usuario_auditoria": "admin"
}
```

**Paso 3: Asignar Atributos a Categoría**
```json
POST /api/v1/categorias-atributos
{
  "categoria_id": "660e8400-e29b-41d4-a716-446655440000",
  "atributo_id": "770e8400-e29b-41d4-a716-446655440000",
  "orden": 1,
  "obligatorio": true,
  "valor_default": "Negro",
  "usuario_auditoria": "admin"
}

POST /api/v1/categorias-atributos
{
  "categoria_id": "660e8400-e29b-41d4-a716-446655440000",
  "atributo_id": "880e8400-e29b-41d4-a716-446655440000",
  "orden": 2,
  "obligatorio": true,
  "valor_default": "M",
  "usuario_auditoria": "admin"
}

POST /api/v1/categorias-atributos
{
  "categoria_id": "660e8400-e29b-41d4-a716-446655440000",
  "atributo_id": "990e8400-e29b-41d4-a716-446655440000",
  "orden": 3,
  "obligatorio": false,
  "valor_default": "Algodón 100%",
  "usuario_auditoria": "admin"
}
```

**Resultado:** La categoría "Camisetas" ahora tiene 3 atributos con valores por defecto. Los productos en esta categoría pueden usar estos valores automáticamente.

### Caso 2: Categoría Jerárquica "Electrónica > Computadoras"

**Paso 1: Crear categoría padre**
```json
POST /api/v1/categorias
{
  "nombre": "Electrónica",
  "es_padre": true,
  "parent_id": null,
  "usuario_auditoria": "admin"
}
```
Respuesta: `id = 550e8400-e29b-41d4-a716-446655440000`

**Paso 2: Crear subcategoría**
```json
POST /api/v1/categorias
{
  "nombre": "Computadoras",
  "es_padre": false,
  "parent_id": "550e8400-e29b-41d4-a716-446655440000",
  "usuario_auditoria": "admin"
}
```

**Resultado:** Se forma la jerarquía: Electrónica (padre) > Computadoras (hija)

---

## Notas de Implementación

### Validación de valor_default

El campo `valor_default` en `CategoriaAtributo` debe cumplir con el `tipo_dato` del atributo asociado:

| tipo_dato | Ejemplo válido | Ejemplo inválido |
|-----------|---|---|
| `string` | `"Negro"`, `"Algodón"` | ❌ (acepta cualquier string) |
| `integer` | `"42"`, `"100"` | `"abc"` |
| `decimal` | `"19.99"`, `"2.5"` | `"abc"` |
| `boolean` | `"true"`, `"false"` | `"sí"` |
| `date` | `"2024-12-31"` | `"31/12/2024"` |

### Soft Delete

Todas las entidades implementan **borrado lógico**:
- Campo `activo: boolean` (default: `true`)
- DELETE endpoint realiza update a `activo=false`
- GET con parámetro `only_active=true` o query implícita filtran registros inactivos

### Auditoría

Todas las entidades registran:
- `creado_en`: Timestamp de creación
- `actualizado_en`: Timestamp de última actualización
- `usuario_auditoria`: Usuario que realizó la acción

### Restricciones Únicas

- `Atributo.nombre` debe ser único (no puede haber dos atributos con el mismo nombre)
- `Categoría.nombre` NO tiene restricción única (permite el mismo nombre en distintos niveles jerárquicos)
- `CategoriaAtributo` puede tener múltiples asignaciones para la misma categoría (diferentes atributos)

### Relaciones Críticas

- Una `Categoría` puede tener múltiples `CategoriaAtributo`
- Un `Atributo` puede asignarse a múltiples `Categoría`s
- Una `Categoría` puede ser padre de múltiples subcategorías
- `CategoriaAtributo` no tiene restricción de unicidad en (categoria_id, atributo_id), permitiendo re-asignaciones
