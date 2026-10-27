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

Las escrituras canónicas ya no aceptan `es_padre`. Las respuestas conservan el
campo legacy y exponen `tiene_hijos`, derivado de hijos activos. La jerarquía
canónica está disponible en `GET /api/v1/categorias/arbol` y las hojas activas
no temporales para selección de categoría en
`GET /api/v1/categorias/seleccionables`; ambos requieren permiso efectivo
`CATEGORIAS.leer`.

**Response 200:**

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "nombre": "Electrónica",
      "es_padre": true,
      "tiene_hijos": true,
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
      "tiene_hijos": false,
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

**GET** `/api/v1/categorias/arbol` devuelve nodos anidados y ordenados por
nombre normalizado e ID. Incluye `id`, `nombre`, `parent_id`, `tiene_hijos`,
`is_default`, `atributos_propios_count`, `atributos_efectivos_count` e `hijos`.
**GET** `/api/v1/categorias/seleccionables` devuelve únicamente hojas activas no
temporales con los conteos de atributos y usa el mismo permiso efectivo.

**GET** `/api/v1/categorias/{item_id}/atributos-efectivos` devuelve una sola
fila por atributo aplicable usando la asignación más cercana de la jerarquía.
Requiere `CATEGORIAS.leer` y `ATRIBUTOS.leer`; el orden explícito va primero
(`orden` ascendente), y las asignaciones sin orden quedan al final por nombre
normalizado e ID. `valor_default: null` y `orden: null` de una asignación hija
son overrides deliberados, no heredan el valor del padre.

**GET** `/api/v1/categorias/{item_id}/atributos-propios` usa los mismos campos,
pero devuelve solo mappings asignados directamente a esa categoría. Ambas rutas
excluyen categorías, mappings y atributos inactivos y devuelven `mapping_id`,
`atributo_id`, `codigo`, `nombre`, `tipo_dato`, `unidad` expandida o `null`,
`restricciones`, `select_options`, `catalog_id`, `obligatorio`,
`valor_default`, `orden`, `categoria_origen` (`id`/`nombre`), `profundidad` y
`heredado`.

**POST** `/api/v1/categorias/{item_id}/atributos` asigna una definición canónica
existente a la categoría con permisos efectivos
`CATEGORIAS.actualizar` + `ATRIBUTOS.leer`. Si ya existe un mapping activo,
devuelve `409 ATTRIBUTE_ALREADY_ASSIGNED`; si el mapping histórico está
inactivo, reactiva la misma identidad. Campos omitidos conservan su configuración
al reactivar y `valor_default: null` limpia el default. La respuesta devuelve el
atributo efectivo actualizado. `aplicar_default_a_existentes` es opt-in y por
omisión es `false` y no escribe valores EAV. `obligatorio` no exige un default;
cuando `valor_default` se envía, el servidor valida tipo, opciones/catálogo y
límites incluso para asignaciones opcionales. En actualizaciones, omitir
`valor_default` conserva su configuración y enviar `null` la limpia.

**POST** `/api/v1/categorias/{item_id}/atributos/previsualizar` calcula el
impacto de una asignación u override sin escribir. **POST**
`/api/v1/categorias/{item_id}/atributos/{mapping_id}/previsualizar` calcula el
impacto de una configuración. Ambos reportan `productos_afectados`,
`productos_faltantes` y nombres/IDs legibles, y devuelven un
`precondicion_preview` firmado por operación, categoría, actor, payload y
definición/mappings/productos/EAV observados. Cambiar ese estado invalida el
token con `409 CATALOG_PREVIEW_STALE`.

Activar obligatoriedad o backfill en la mutación final requiere la precondición
vigente. Si quedan faltantes sin backfill explícito válido, se devuelve
`409 PRODUCT_REQUIRED_ATTRIBUTES_MISSING` con IDs accionables y se revierte
toda escritura. El backfill es fill-only; los valores existentes se conservan.
Si existe una identidad EAV inactiva, se reactiva con el mismo ID solo cuando su
valor histórico sigue siendo válido para la definición actual; se registra la
recuperación en auditoría y no se reemplaza ese valor por el default. Una fila
histórica incompatible permanece intacta y no se sobrescribe silenciosamente.
Una conversión global que vuelva incompatible un valor efectivo obligatorio
también se bloquea, mientras que los remapeos opcionales mantienen su flujo
reversible.

**PUT** `/api/v1/categorias/{item_id}/atributos/{mapping_id}` actualiza solo
`orden`, `obligatorio` y `valor_default` del mapping activo perteneciente a la
categoría indicada. Requiere `CATEGORIAS.actualizar` + `ATRIBUTOS.leer`; el
servidor registra el actor autenticado. El DTO rechaza campos de definición
global como `nombre`, `codigo`, `tipo_dato`, `unidad_id` y restricciones.
Configurar un atributo heredado crea o reactiva un mapping local mediante el
POST anterior con el mismo `atributo_id`; no modifica el mapping de origen.

**POST** `/api/v1/categorias/{item_id}/atributos/{mapping_id}/previsualizar-remocion`
simula quitar solo el mapping propio. Informa productos afectados, valores que
se conservarán porque el atributo sigue aplicando, valores que dejarán de aplicar
y faltantes obligatorios del esquema resultante. **DELETE**
`/api/v1/categorias/{item_id}/atributos/{mapping_id}` requiere
`{"confirmar": true, "precondicion_preview": "..."}`. Si el preview quedó stale,
faltan valores obligatorios o existen remapeos pendientes, responde 409 sin
mutar mapping ni EAV. Los valores que ya no aplican se desactivan lógicamente y
se auditan; la baja global del atributo es una operación distinta.

`POST /api/v1/atributos` con `categoria_id` crea la definición y su mapping en
una transacción exterior única; si falla cualquiera de los dos pasos, ninguno
persiste. Requiere `CATEGORIAS.actualizar` + `ATRIBUTOS.leer` + `ATRIBUTOS.crear`.
Cuando la creación hace obligatorio el atributo o solicita backfill, requiere
una precondición vigente de **POST** `/api/v1/atributos/previsualizar`, que
simula la definición y el mapping sin insertar filas. El token liga actor,
categoría, definición/defaults y estado efectivo de productos/EAV; un cambio o
expiración devuelve `409 CATALOG_PREVIEW_STALE`. Los faltantes sin default
explícito y consentimiento de backfill devuelven
`409 PRODUCT_REQUIRED_ATTRIBUTES_MISSING` y revierten la transacción completa.

Ejemplo de atributo numérico efectivo:

```json
{
  "mapping_id": "550e8400-e29b-41d4-a716-446655440001",
  "atributo_id": "550e8400-e29b-41d4-a716-446655440002",
  "codigo": "almacenamiento",
  "nombre": "Almacenamiento",
  "tipo_dato": "integer",
  "unidad": {
    "id": "550e8400-e29b-41d4-a716-446655440003",
    "codigo": "GB",
    "nombre": "Gigabyte",
    "simbolo": "GB",
    "magnitud_codigo": "DATA_STORAGE"
  },
  "restricciones": {
    "allow_negative": false,
    "min_value": 0,
    "max_value": 4096
  },
  "select_options": null,
  "catalog_id": null,
  "obligatorio": true,
  "valor_default": null,
  "orden": 1,
  "categoria_origen": {
    "id": "550e8400-e29b-41d4-a716-446655440004",
    "nombre": "Mouse"
  },
  "profundidad": 0,
  "heredado": false
}
```

La validación EAV legacy y el esqueleto de atributos de Producto reutilizan el
mismo resolver. Si el puente de categorías de un Producto contiene varias
categorías que no pertenecen a una única cadena ancestro-descendiente, el
backend responde `409 CATEGORY_ATTRIBUTE_SCOPE_AMBIGUOUS` y no combina ramas;
la clasificación debe revisarse antes de guardar o validar atributos.

**POST** `/api/v1/categorias/{item_id}/reactivar` reactiva una categoría
ordinaria inactiva conservando su ID. No reactiva productos ni asignaciones.
El bucket `Sin clasificar` se administra únicamente por la regla interna B3.

Al crear una hija o mover una categoría bajo un padre con productos directos,
la UI debe solicitar primero `POST /api/v1/categorias/previsualizar` o
`POST /api/v1/categorias/{item_id}/previsualizar`. Si el preview informa
`requiere_confirmacion`, la confirmación reenvía `{payload, confirmar_b3: true,
precondicion_preview}` a `POST /api/v1/categorias` o `PUT
/api/v1/categorias/{item_id}`. El token liga actor, operación, payload y estado
de productos/bucket; un cambio responde `CATALOG_PREVIEW_STALE` y exige un
preview nuevo. B3 mueve solo la clasificación; no modifica cantidades ni
documentos.

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
  "parent_id": "550e8400-e29b-41d4-a716-446655440000"
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

Actualiza parcialmente nombre y/o `parent_id`. Enviar `parent_id: null` mueve a raíz.
`es_padre` se ignora como entrada legacy; el servidor deriva `tiene_hijos`.

**Parámetros de Path:**

- `item_id` (UUID) - ID de la categoría

**Request Body:**

```json
{
  "nombre": "Computadoras de Escritorio"
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

| Campo               | Tipo        | Restricción                     | Descripción                                                                                |
| ------------------- | ----------- | ------------------------------- | ------------------------------------------------------------------------------------------ |
| `id`                | UUID        | PK, Auto                        | Identificador único de la categoría                                                        |
| `nombre`            | String(255) | Not Null, Index                 | Nombre descriptivo de la categoría (ej: "Electrónica", "Computadoras", "Ropa")             |
| `es_padre`          | Boolean     | Default: false, Not Null        | Indicador de si esta categoría es padre de subcategorías. Facilita consultas jerárquicas.  |
| `parent_id`         | UUID        | FK (tbl_categoria.id), Optional | Referencia a la categoría padre si es una subcategoría. Si es nula, es una categoría raíz. |
| `activo`            | Boolean     | Default: true                   | Indicador de estado (soft delete)                                                          |
| `creado_en`         | DateTime    | Auto                            | Timestamp de creación                                                                      |
| `actualizado_en`    | DateTime    | Auto                            | Timestamp de última actualización                                                          |
| `usuario_auditoria` | String      | Optional                        | Usuario que realizó la acción                                                              |

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
- `select` - opción de una lista fija almacenada en `select_options`
- `catalog` - valor activo de `catalog_id` en `/api/v1/catalogos`

Los atributos numéricos admiten `allow_negative`, `min_value` y `max_value`. Los nombres se comparan sin distinguir mayúsculas/espacios dentro de la rama efectiva; se permiten nombres iguales en ramas independientes y asignar el mismo atributo a un ancestro e hijo constituye un override.

Cuando cambia el tipo, los valores convertibles se mueven a la columna tipada nueva. Los valores incompatibles se conservan en su columna anterior y generan elementos auditables en `/api/v1/atributos/remapeos/pendientes`; se resuelven mediante `POST /api/v1/atributos/remapeos/resolver`.

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
  "tipo_dato": "select",
  "select_options": ["Rojo", "Azul", "Negro"],
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

Requiere primero **POST** `/api/v1/atributos/{item_id}/previsualizar-baja` y
confirmación con `{ "payload": { "confirmar": true }, "precondicion_preview":
"..." }`. La precondición liga actor y estado completo de definición,
asignaciones, valores EAV y remapeos. El token vencido o estado cambiado devuelve
`409 CATALOG_PREVIEW_STALE`; remapeos pendientes bloquean la baja con
`ATTRIBUTE_HAS_PENDING_REMAPS`. La baja lógica y el snapshot son atómicos; las
asignaciones y valores históricos conservan su identidad.

**GET** `/api/v1/atributos/{item_id}/reversion` devuelve la operación más
reciente y disponibilidad de undo/reactivación. **POST**
`/api/v1/atributos/{item_id}/revertir` y `/reactivar` restauran únicamente el
snapshot intacto; un estado posterior cambiado devuelve `409 ATTRIBUTE_STATE_CHANGED`.
Un atributo legacy inactivo sin snapshot devuelve `LEGACY_ATTRIBUTE_NO_SNAPSHOT`
y requiere recuperación administrativa, sin reactivación parcial.

**Response 204:** No content

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo               | Tipo        | Restricción             | Descripción                                                                                             |
| ------------------- | ----------- | ----------------------- | ------------------------------------------------------------------------------------------------------- |
| `id`                | UUID        | PK, Auto                | Identificador único del atributo                                                                        |
| `nombre`            | String(120) | Unique, Not Null, Index | Nombre único del atributo (ej: "Color", "Tamaño", "Material", "Peso", "Garantía")                       |
| `tipo_dato`         | Enum        | Not Null                | Tipo de dato: `string`, `integer`, `decimal`, `boolean`, `date`. Define el formato esperado en valores. |
| `activo`            | Boolean     | Default: true           | Indicador de estado                                                                                     |
| `creado_en`         | DateTime    | Auto                    | Timestamp de creación                                                                                   |
| `actualizado_en`    | DateTime    | Auto                    | Timestamp de última actualización                                                                       |
| `usuario_auditoria` | String      | Optional                | Usuario auditor                                                                                         |

---

## 3. Categoría-Atributo

### Descripción

Tabla de asignación que vincula atributos a categorías, permitiendo caracterizar dinámicamente productos pertenecientes a esa categoría. Cada asignación puede definir:

- **orden**: Posición visual para mostrar atributos en formularios o listados
- **obligatorio**: Si el atributo debe tener un valor en todos los productos de la categoría
- **valor_default**: Valor por defecto que se asigna automáticamente si no se proporciona otro

**Compatibilidad legacy de asignaciones:** `GET /api/v1/categorias-atributos` y `GET /api/v1/categorias-atributos/{id}` se conservan temporalmente para consumidores de lectura y requieren `ATRIBUTOS.leer`. `POST`, `PUT` y `DELETE` sobre estas rutas responden `410 Gone` con `LEGACY_CATEGORY_ATTRIBUTE_WRITE_DISABLED`; no realizan escrituras. Administre las relaciones con los endpoints efectivos/propios y las operaciones contextuales de `/api/v1/categorias/{id}/atributos`, que validan permiso, preview y precondición.

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

**GET (deprecated)** `/api/v1/categorias-atributos`

Obtiene asignaciones directas para compatibilidad temporal; exige `ATRIBUTOS.leer`. Para el panel use los endpoints efectivos/propios indicados arriba.

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

**GET (deprecated)** `/api/v1/categorias-atributos/{id}`

Obtiene una asignación directa para compatibilidad temporal; exige `ATRIBUTOS.leer`.

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

  <TabItem value="post" label="POST legacy (410)">

**POST deshabilitado** `/api/v1/categorias-atributos`

Devuelve HTTP `410 Gone` con el código estable `LEGACY_CATEGORY_ATTRIBUTE_WRITE_DISABLED`. No crea asignaciones. Use `POST /api/v1/categorias/{id}/atributos` y su preview cuando se requiera confirmación.

```json
{
  "code": "LEGACY_CATEGORY_ATTRIBUTE_WRITE_DISABLED",
  "message": "Utilice las operaciones contextuales de la categoría."
}
```

  </TabItem>

  <TabItem value="put" label="PUT legacy (410)">

**PUT deshabilitado** `/api/v1/categorias-atributos/{id}`

Devuelve HTTP `410 Gone` con `LEGACY_CATEGORY_ATTRIBUTE_WRITE_DISABLED`. Configure la relación con `PUT /api/v1/categorias/{id}/atributos/{mapping_id}` y su preview contextual.

```json
{
  "code": "LEGACY_CATEGORY_ATTRIBUTE_WRITE_DISABLED",
  "message": "Utilice las operaciones contextuales de la categoría."
}
```

  </TabItem>

  <TabItem value="delete" label="DELETE legacy (410)">

**DELETE deshabilitado** `/api/v1/categorias-atributos/{id}`

Devuelve HTTP `410 Gone` con `LEGACY_CATEGORY_ATTRIBUTE_WRITE_DISABLED`. Para quitar una asignación use `DELETE /api/v1/categorias/{id}/atributos/{mapping_id}` con preview y precondición firmada.

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo               | Tipo     | Restricción                     | Descripción                                                                                                                                                                                         |
| ------------------- | -------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                | UUID     | PK, Auto                        | Identificador único de la asignación                                                                                                                                                                |
| `categoria_id`      | UUID     | FK (tbl_categoria.id), Not Null | Referencia a la categoría que recibe el atributo                                                                                                                                                    |
| `atributo_id`       | UUID     | FK (tbl_atributo.id), Not Null  | Referencia al atributo asignado                                                                                                                                                                     |
| `orden`             | Integer  | Optional                        | Número de orden para mostrar el atributo en formularios (ej: 1, 2, 3...). Facilita el ordenamiento visual.                                                                                          |
| `obligatorio`       | Boolean  | Optional                        | Si `true`, el atributo debe tener un valor en todo producto de esta categoría. Si `false` o nulo, es opcional.                                                                                      |
| `valor_default`     | String   | Optional                        | Valor por defecto que se asigna automáticamente si no se proporciona otro. **Validación**: Debe cumplir el `tipo_dato` del atributo (ej: si tipo_dato="integer", valor_default debe ser un número). |
| `usuario_auditoria` | String   | Optional                        | Usuario que realizó la acción                                                                                                                                                                       |
| `activo`            | Boolean  | Default: true                   | Indicador de estado                                                                                                                                                                                 |
| `creado_en`         | DateTime | Auto                            | Timestamp de creación                                                                                                                                                                               |
| `actualizado_en`    | DateTime | Auto                            | Timestamp de última actualización                                                                                                                                                                   |

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

Use `POST /api/v1/atributos` para crear y asignar una definición, o `POST /api/v1/categorias/{id}/atributos` para reutilizar una existente. Cuando sea obligatorio o se solicite backfill, genere el preview contextual y confirme el token vigente. Las antiguas llamadas `POST /api/v1/categorias-atributos` responden `410 LEGACY_CATEGORY_ATTRIBUTE_WRITE_DISABLED`.

**Resultado:** La categoría recibe los atributos efectivos con defaults explícitos y productos activos validados por el backend.

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

| tipo_dato | Ejemplo válido         | Ejemplo inválido             |
| --------- | ---------------------- | ---------------------------- |
| `string`  | `"Negro"`, `"Algodón"` | ❌ (acepta cualquier string) |
| `integer` | `"42"`, `"100"`        | `"abc"`                      |
| `decimal` | `"19.99"`, `"2.5"`     | `"abc"`                      |
| `boolean` | `"true"`, `"false"`    | `"sí"`                       |
| `date`    | `"2024-12-31"`         | `"31/12/2024"`               |

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
