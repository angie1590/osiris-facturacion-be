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
- `only_active=false` incluye activos e inactivos; para solo inactivos se usa `estado=inactivo`.

## Estructura General

El Directorio está compuesto por estas entidades y la cuenta Usuario, documentada en [Seguridad y Accesos](./seguridad-accesos):

1. **Persona** - Identidad natural global con validación local de identificación, sin certificar existencia o estado SRI.
2. **Cliente** - Asociación entre una Persona y un Tipo de Cliente.
3. **Tipo de Cliente** - Catálogo de categorías de cliente con descuentos.
4. **Proveedor Persona** - Registro de proveedores que son personas naturales.
5. **Proveedor Sociedad** - Registro de proveedores que son empresas.
6. **Empleado** - Vinculación de personas como empleados de una Empresa, con Usuario creado en la misma transacción.

Persona es global y exclusivamente natural. Cliente, Proveedor Persona, Empleado y Usuario tienen una FK `persona_id` única (1:1 por rol); los roles pueden coexistir. Sociedad guarda identidad jurídica propia y contacto natural mutable (1:N). No hay herencia ORM ni identidad duplicada en los roles.

### Contrato compuesto y Search-or-Create

| Operación                             | Alternativas excluyentes                           | Datos adicionales                                                         |
| ------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------- |
| POST /api/v1/clientes                 | `persona_id` XOR `persona_nueva`                   | `tipo_cliente_id` activo                                                  |
| POST /api/v1/proveedores-persona      | `persona_id` XOR `persona_nueva`                   | RUC natural y TipoContribuyente compatible activo                         |
| POST /api/v1/empleados                | `persona_id` XOR `persona_nueva`                   | Empresa activa/autorizada, datos laborales y bloque `usuario` obligatorio |
| POST /api/v1/usuarios                 | `persona_id` XOR `persona_nueva`                   | `rol_id`, `username`, `password`; no exige Empleado                       |
| POST /api/v1/proveedores-sociedad     | `persona_contacto_id` XOR `persona_contacto_nueva` | Identidad jurídica, dirección, email y catálogo activo                    |
| PUT /api/v1/proveedores-sociedad/{id} | Como máximo una alternativa de contacto            | Omitir ambas conserva el contacto; no admite contacto nulo                |

En POST debe existir exactamente una alternativa no nula: ambas o ninguna producen `422`. `persona_nueva` y `persona_contacto_nueva` usan PersonaCreate. Su `usuario_auditoria` es opcional por compatibilidad técnica, no un input de producción: el actor autoritativo es el JWT. Los ejemplos por ID siguen vigentes; los ejemplos Read muestran campos base, no la proyección completa.

Ejemplo de alta contextual, sin guardar Persona previamente:

```json
{
  "persona_nueva": {
    "tipo_identificacion": "PASAPORTE",
    "identificacion": "AB12345",
    "nombre": "Ana",
    "apellido": "Perez"
  },
  "tipo_cliente_id": "660e8400-e29b-41d4-a716-446655440000"
}
```

El resolver normaliza y busca incluyendo inactivos. Reutiliza Persona activa sin sobrescribir sus datos; una inactiva devuelve `409` con `persona_id` y acción `reactivar`. Si falta, inserta dentro de la unidad de trabajo del rol. Un único commit exterior guarda Persona y rol (también Usuario al crear Empleado); cualquier fallo revierte la operación, sin Persona huérfana. Ante carrera por la restricción específica de identificación, un savepoint permite reutilizar la ganadora activa sin sobrescribirla; otras violaciones no se tratan como coincidencia. El rol duplicado devuelve `409`, incluso si está inactivo, y requiere acción explícita.

La UI común conserva el borrador y los campos del formulario padre ante cancelación de Persona o errores. Completar Persona no persiste: el submit del rol envía una sola petición compuesta, nunca POST Persona seguido de POST rol. El maestro Personas sí permite alta independiente.

### Permisos efectivos y consultas

Cada entidad tiene módulo propio: `PERSONAS`, `TIPOS_CLIENTE`, `CLIENTES`, `PROVEEDORES_PERSONA`, `PROVEEDORES_SOCIEDAD`, `EMPLEADOS`, `USUARIOS`. GET exige `leer`, POST de alta `crear`, PUT y reactivación `actualizar`, DELETE `eliminar`. El resolver exige además `PERSONAS.leer` y, solo si inserta Persona, `PERSONAS.crear`. Alta Empleado exige también `USUARIOS.crear`. Un nombre de rol no autoriza una llamada; el backend comprueba los permisos efectivos.

Los listados admiten `q`, `estado`, `sort_by` y dirección permitida, además de `limit`, `offset`, `only_active`; Persona y roles con identidad admiten `identificacion` exacta normalizada. Persona usa `sort_direction`; comerciales y Usuario admiten `sort_order`/`sort_direction`, Empleado expone `sort_order`. No asumir que todos comparten los mismos campos ordenables: se aplica whitelist por recurso y un orden inválido devuelve `422`. `items` y `meta.total` proceden del servidor; no filtrar una página local como si fuera el directorio completo.

- GET /api/v1/personas/contrato: devuelve OpenAPI de la aplicación por el prefijo API autenticado; exige `PERSONAS.leer`. La UI verifica allí soporte compuesto antes de habilitar el submit.
- GET /api/v1/personas/{id}/vinculos: exige `PERSONAS.leer`; devuelve `persona_id`, `cliente`, `proveedor_persona`, `empleado`, `usuario`, `proveedores_sociedad` y `dependencias_activas`. Cada rol visible contiene `id`/`activo`; sociedades incluyen `razon_social`. Sin permiso de lectura del módulo correspondiente se ocultan sus detalles, pero se conserva la dependencia bloqueante con ID nulo.

Las proyecciones Read comerciales incluyen `persona` (también el contacto de Sociedad), nombre del catálogo y metadatos `created_by`, `updated_by`, `created_at`, `updated_at`, además de los campos base. Cliente incluye `tipo_cliente_nombre` y `descuento`; proveedores, `tipo_contribuyente_nombre`. Empleado incluye `persona`; Usuario incluye `persona`, `rol_nombre`, `tiene_codigo_aprobacion` y alias `codigo_aprobacion_configurado`. No asumir metadatos adicionales en PersonaRead, EmpleadoRead o UsuarioRead, ni hashes/secretos en ningún Read.

### Baja y reactivación explícitas

DELETE Persona devuelve `409` mientras exista Cliente, Proveedor Persona, Empleado, Usuario o Sociedad-contacto activo; TipoCliente también bloquea baja con Clientes activos. Bajar Cliente/proveedores no baja Persona ni contacto. Los cambios efectivos de `persona_id` en Cliente, Proveedor Persona, Empleado y Usuario, y de `username` en Usuario, devuelven `409`; no se ignoran. `rol_id` de Usuario puede cambiar a un Rol activo. `activo` no es un bypass aceptado por PUT.

| Acción                      | Endpoint                                         | Resultado                                           |
| --------------------------- | ------------------------------------------------ | --------------------------------------------------- |
| Reactivar Persona           | POST /api/v1/personas/{id}/reactivar             | Mismo ID, revalidación y auditoría                  |
| Reactivar TipoCliente       | POST /api/v1/tipos-cliente/{id}/reactivar        | Mismo ID y validación del catálogo                  |
| Reactivar Cliente           | POST /api/v1/clientes/{id}/reactivar             | Persona y TipoCliente activos                       |
| Reactivar Proveedor Persona | POST /api/v1/proveedores-persona/{id}/reactivar  | Persona activa, RUC natural y catálogo compatible   |
| Reactivar Sociedad          | POST /api/v1/proveedores-sociedad/{id}/reactivar | Contacto activo, RUC jurídico y catálogo compatible |
| Reactivar Empleado          | POST /api/v1/empleados/{id}/reactivar            | Empresa/Persona activas; no reactiva Usuario        |

DELETE Empleado desactiva Empleado y Usuario asociado e invalida access/refresh mediante `sesion_invalidada_en` en una transacción; no altera Persona ni roles comerciales. Usuario previo al alta Empleado produce conflicto administrativo: no se duplican cuentas ni sobrescriben credenciales. Restaurar acceso requiere la acción separada descrita en [Seguridad](./seguridad-accesos).

Errores transversales: `400` regla funcional, `401` autenticación, `403` permiso/contexto, `404` referencia ausente, `409` duplicado/inactivo/dependencia/inmutabilidad, `422` DTO/filtro inválido. `detail` puede ser texto, objeto o lista de errores; conservarlo y no sustituir conflictos por un error genérico.

---

## 1. Persona

### Descripción

Tabla central de personas naturales con validación local de documentos de identificación:

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

Crea una nueva persona con validación local de identificación; no consulta existencia o estado tributario SRI.

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
  "email": "juan.perez@ejemplo.com"
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

**Response 422 (Validación local del DTO fallida):**

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

Actualiza parcialmente una persona. Al enviar identificación o tipo, se deben enviar ambos para revalidar la combinación completa.

**Parámetros de Path:**

- `id` (UUID) - ID de la persona

**Request Body:**

```json
{
  "nombre": "Juan Carlos",
  "apellido": "Pérez Rodríguez",
  "email": "juan.carlos@ejemplo.com"
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

| Campo                 | Tipo        | Restricción      | Descripción                                                                                      |
| --------------------- | ----------- | ---------------- | ------------------------------------------------------------------------------------------------ |
| `id`                  | UUID        | PK, Auto         | Identificador único de la persona                                                                |
| `identificacion`      | String(50)  | Unique, Not Null | Documento normalizado, con validación local de cédula o RUC natural; no certifica estado SRI.    |
| `tipo_identificacion` | Enum        | Not Null         | Tipo: `CEDULA` (10 dígitos), `RUC` (13 dígitos persona natural), `PASAPORTE` (mín. 5 caracteres) |
| `nombre`              | String(120) | Not Null         | Nombre de la persona                                                                             |
| `apellido`            | String(120) | Not Null         | Apellido de la persona                                                                           |
| `direccion`           | String(255) | Optional         | Domicilio                                                                                        |
| `telefono`            | String(30)  | Optional         | Número de contacto                                                                               |
| `ciudad`              | String(120) | Optional         | Ciudad de residencia                                                                             |
| `email`               | Email       | Optional         | Correo electrónico (formato válido)                                                              |
| `activo`              | Boolean     | Default: true    | Indicador de estado (soft delete)                                                                |
| `creado_en`           | DateTime    | Auto             | Timestamp de creación                                                                            |
| `actualizado_en`      | DateTime    | Auto             | Timestamp de última actualización                                                                |
| `usuario_auditoria`   | String      | Not Null         | Usuario que realizó la acción                                                                    |

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
      "descuento": 15.5,
      "activo": true,
      "creado_en": "2024-01-10T09:00:00Z",
      "actualizado_en": "2024-01-10T09:00:00Z",
      "usuario_auditoria": "admin"
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "nombre": "Cliente Minorista",
      "descuento": 5.0,
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
  "descuento": 15.5,
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
  "descuento": 20.0
}
```

**Response 201:**

```json
{
  "id": "880e8400-e29b-41d4-a716-446655440000",
  "nombre": "Cliente Especial",
  "descuento": 20.0,
  "activo": true,
  "creado_en": "2024-01-16T11:45:00Z",
  "actualizado_en": "2024-01-16T11:45:00Z",
  "usuario_auditoria": "admin"
}
```

**Response 422 (Descuento fuera de rango en DTO):**

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "descuento"],
      "msg": "Input should be less than or equal to 100",
      "input": 150.0
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
  "descuento": 18.0
}
```

**Response 200:**

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "nombre": "Cliente Mayorista",
  "descuento": 18.0,
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

| Campo               | Tipo         | Restricción                | Descripción                                                       |
| ------------------- | ------------ | -------------------------- | ----------------------------------------------------------------- |
| `id`                | UUID         | PK, Auto                   | Identificador único                                               |
| `nombre`            | String(255)  | Unique, Not Null           | Nombre de la categoría (ej: "Mayorista", "Minorista", "Especial") |
| `descuento`         | Decimal(5,2) | Default: 0, Range: [0-100] | Porcentaje de descuento base aplicable a este tipo de cliente     |
| `activo`            | Boolean      | Default: true              | Indicador de estado                                               |
| `creado_en`         | DateTime     | Auto                       | Timestamp de creación                                             |
| `actualizado_en`    | DateTime     | Auto                       | Timestamp de última actualización                                 |
| `usuario_auditoria` | String       | Not Null                   | Usuario auditor                                                   |

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
  "tipo_cliente_id": "660e8400-e29b-41d4-a716-446655440000"
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

**Response 404 (Persona referenciada no existe):**

```json
{
  "detail": "Persona no encontrada"
}
```

  </TabItem>

  <TabItem value="put" label="Actualizar Cliente">

**PUT** `/api/v1/clientes/{id}`

Actualiza el tipo de cliente asociado. No se puede cambiar la persona.

**Request Body:**

```json
{
  "tipo_cliente_id": "770e8400-e29b-41d4-a716-446655440000"
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

| Campo               | Tipo     | Restricción                           | Descripción                                                                                                   |
| ------------------- | -------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `id`                | UUID     | PK, Auto                              | Identificador único del cliente                                                                               |
| `persona_id`        | UUID     | FK (tbl_persona.id), Unique, Not Null | Referencia a la persona vinculada como cliente. **Restricción**: Cada persona solo puede ser cliente una vez. |
| `tipo_cliente_id`   | UUID     | FK (tbl_tipo_cliente.id), Not Null    | Referencia a la categoría de cliente                                                                          |
| `activo`            | Boolean  | Default: true                         | Indicador de estado                                                                                           |
| `creado_en`         | DateTime | Auto                                  | Timestamp de creación                                                                                         |
| `actualizado_en`    | DateTime | Auto                                  | Timestamp de última actualización                                                                             |
| `usuario_auditoria` | String   | Optional                              | Usuario auditor                                                                                               |

---

## 4. Proveedor Persona

### Descripción

Registro de proveedores que son personas naturales. Debe estar vinculado a una Persona y contiene información comercial específica del proveedor.

Reglas de negocio backend (importantes para frontend):

- `persona_id` debe apuntar a una Persona con `tipo_identificacion = RUC`.
- El RUC de la persona debe ser de persona natural válido (no sociedad).
- El catálogo debe estar activo y tener `aplica_persona_natural=true`; no se infiere por nombre ni se excluye `04` cuando su flag aprobado permite natural.
- En `PUT`, un cambio efectivo de `persona_id` devuelve `409`; no se ignora silenciosamente.

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
  "persona_id": "550e8400-e29b-41d4-a716-446655440000"
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
  "nombre_comercial": "Distribuidora Pérez, López y Asociados"
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

| Campo                   | Tipo        | Restricción                                  | Descripción                                                                      |
| ----------------------- | ----------- | -------------------------------------------- | -------------------------------------------------------------------------------- |
| `id`                    | UUID        | PK, Auto                                     | Identificador único                                                              |
| `nombre_comercial`      | String(255) | Optional                                     | Nombre bajo el cual opera comercialmente el proveedor                            |
| `tipo_contribuyente_id` | String(2)   | FK (aux_tipo_contribuyente.codigo), Not Null | Clasificación SRI del contribuyente (ej: "01" = Persona Natural, "02" = Empresa) |
| `persona_id`            | UUID        | FK (tbl_persona.id), Unique, Not Null        | Una sola asociación Proveedor Persona por identidad, incluyendo inactivos        |
| `activo`                | Boolean     | Default: true                                | Indicador de estado                                                              |
| `creado_en`             | DateTime    | Auto                                         | Timestamp de creación                                                            |
| `actualizado_en`        | DateTime    | Auto                                         | Timestamp de última actualización                                                |
| `usuario_auditoria`     | String      | Not Null                                     | Usuario auditor                                                                  |

---

## 5. Proveedor Sociedad

### Descripción

Registro de proveedores que son empresas (sociedades). Contiene información detallada de la empresa y requiere un RUC válido de 13 dígitos.

Reglas de negocio backend (importantes para frontend):

- El `ruc` debe ser válido y no puede ser RUC de persona natural.
- El catálogo debe estar activo y tener `aplica_sociedad=true`.
- `telefono`, si se envía, debe tener exactamente 10 dígitos numéricos.
- `email` debe cumplir formato válido.
- En `PUT`, el contacto es mutable: enviar `persona_contacto_id` o `persona_contacto_nueva`, nunca ambos. Sin alternativa se conserva el contacto; el cambio y el contacto nuevo se guardan juntos.

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
  "persona_contacto_id": "550e8400-e29b-41d4-a716-446655440000"
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

**Response 422 (RUC inválido en DTO):**

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

Actualiza un proveedor sociedad; permite cambiar el contacto natural existente o crear uno nuevo en la misma transacción, sin modificar la Persona anterior.

**Request Body:**

```json
{
  "razon_social": "Distribuidora Nacional de Productos S.A.",
  "nombre_comercial": "DistNac Premium"
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
  "telefono": "0222222222",
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

| Campo                   | Tipo        | Restricción                                  | Descripción                                                                             |
| ----------------------- | ----------- | -------------------------------------------- | --------------------------------------------------------------------------------------- |
| `id`                    | UUID        | PK, Auto                                     | Identificador único                                                                     |
| `ruc`                   | String(13)  | Unique, Not Null, Exactly 13                 | RUC jurídico validado localmente; no es la cédula del contacto ni certifica estado SRI. |
| `razon_social`          | String(255) | Not Null                                     | Nombre legal de la empresa registrado en SRI                                            |
| `nombre_comercial`      | String(255) | Optional                                     | Nombre comercial bajo el que opera                                                      |
| `direccion`             | String(255) | Not Null                                     | Domicilio principal de la empresa                                                       |
| `telefono`              | String      | Optional                                     | Si se envía, debe tener exactamente 10 dígitos numéricos.                               |
| `email`                 | Email       | Not Null                                     | Correo electrónico principal (formato válido)                                           |
| `tipo_contribuyente_id` | String(2)   | FK (aux_tipo_contribuyente.codigo), Not Null | Catálogo activo con `aplica_sociedad=true`.                                             |
| `persona_contacto_id`   | UUID        | FK (tbl_persona.id), Not Null                | Contacto natural activo y mutable; una Persona puede contactar varias sociedades.       |
| `activo`                | Boolean     | Default: true                                | Indicador de estado                                                                     |
| `creado_en`             | DateTime    | Auto                                         | Timestamp de creación                                                                   |
| `actualizado_en`        | DateTime    | Auto                                         | Timestamp de última actualización                                                       |
| `usuario_auditoria`     | String      | Not Null                                     | Usuario auditor                                                                         |

---

## 6. Empleado

### Descripción

Vinculación única global de una Persona como Empleado de una Empresa. Incluye datos laborales y exige crear Usuario asociado en la misma unidad de trabajo.

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
      "salario": 1500.0,
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
  "salario": 1500.0,
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
  "salario": 1500.0,
  "fecha_ingreso": "2024-01-01",
  "fecha_nacimiento": "1990-06-15",
  "foto": "https://storage.example.com/empleados/juan_perez.jpg",
  "usuario": {
    "username": "jperez",
    "password": "MiContraseñaSegura123!",
    "rol_id": "eee0e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Response 201:**

```json
{
  "id": "ccc0e8400-e29b-41d4-a716-446655440000",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "empresa_id": "ddd0e8400-e29b-41d4-a716-446655440000",
  "salario": 1500.0,
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

**Response 422 (Edad mínima no cumplida en DTO, default EMP_MIN_AGE=16):**

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

**Response 422 (Fecha de salida anterior a ingreso en DTO):**

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
  "salario": 1800.0,
  "fecha_salida": "2024-12-31"
}
```

**Response 200:**

```json
{
  "id": "ccc0e8400-e29b-41d4-a716-446655440000",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "empresa_id": "ddd0e8400-e29b-41d4-a716-446655440000",
  "salario": 1800.0,
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

Realiza la baja lógica de Empleado y Usuario asociado e invalida sus sesiones en una transacción, sin desactivar Persona.

**Response 204:** No content

  </TabItem>
</Tabs>

### Diccionario de Datos

| Campo               | Tipo          | Restricción                           | Descripción                                                                                                           |
| ------------------- | ------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `id`                | UUID          | PK, Auto                              | Identificador único                                                                                                   |
| `persona_id`        | UUID          | FK (tbl_persona.id), Unique, Not Null | Referencia a la Persona vinculada. Cada persona solo puede ser empleado una vez.                                      |
| `empresa_id`        | UUID          | FK (tbl_empresa.id), Not Null         | Referencia a la Empresa que lo emplea                                                                                 |
| `salario`           | Decimal(10,2) | Not Null, no negativo                 | Salario mensual en USD, hasta dos decimales                                                                           |
| `fecha_ingreso`     | Date          | Not Null                              | Fecha de inicio laboral. No puede ser futura.                                                                         |
| `fecha_nacimiento`  | Date          | Optional                              | Fecha de nacimiento. Si se proporciona, se valida **edad mínima** (default EMP_MIN_AGE=16, configurable por env var). |
| `fecha_salida`      | Date          | Optional                              | Fecha de cese laboral. Si está presente, debe ser posterior a fecha_ingreso.                                          |
| `foto`              | String(500)   | Optional                              | URL o ruta a foto del empleado                                                                                        |
| `activo`            | Boolean       | Default: true                         | Indicador de estado                                                                                                   |
| `creado_en`         | DateTime      | Auto                                  | Timestamp de creación                                                                                                 |
| `actualizado_en`    | DateTime      | Auto                                  | Timestamp de última actualización                                                                                     |
| `usuario_auditoria` | String        | Optional                              | Usuario auditor                                                                                                       |

---

## Validación Local y Aplicabilidad Tributaria

### Persona: Tipos de Identificación

1. **CEDULA** (10 dígitos)

- Identidad natural, con algoritmo local vigente de cédula; no se modifica en este refactor.
- Los números de los ejemplos JSON son ilustrativos, no documentos certificados ni necesariamente aceptados por el validador.

2. **RUC** (13 dígitos, para personas naturales)
   - Compuesto por: 10 primeros dígitos (cédula) + 3 dígitos de secuencia
   - Aplicable a personas naturales que son contribuyentes

- Se valida con la política local vigente de RUC natural, no como RUC jurídico.

3. **PASAPORTE** (mín. 5 caracteres)
   - Documento internacional

- Normalización: trim y mayúsculas; mínimo 5 caracteres.

### Proveedor Sociedad: RUC Empresas

- **RUC** (13 dígitos exactos)
- Aplicable a empresas/sociedades comerciales
- No se deriva de la identificación de la Persona contacto; se valida como RUC no natural según la política local vigente.

La normalización compartida aplica trim, elimina espacios y convierte a mayúsculas; cédula/RUC deben cumplir la estructura numérica del validador, sin convertir letras o signos en dígitos. Pasar estructura/algoritmo local no prueba existencia, actividad o inscripción SRI. Las reglas de cada comprobante y su autorización son una capa separada; no se cambian algoritmos tributarios ni FE-EC.

### Tipo Contribuyente

TipoContribuyente expone `aplica_persona_natural` y `aplica_sociedad`. Backfill aprobado de `f8b2c5d30e71`:

| Código      | Natural | Sociedad |
| ----------- | ------- | -------- |
| `01`, `03`  | Sí      | No       |
| `02`, `05`  | No      | Sí       |
| `04`        | Sí      | Sí       |
| Desconocido | No      | No       |

Los servicios consultan flags y `activo`, no el texto del nombre ni una inferencia libre de códigos.

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
- `usuario_auditoria`: actor derivado del contexto autenticado; no se solicita en formularios productivos. Su aceptación opcional para scripts/tests confiables no permite suplantar el JWT.

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

### Preflight y migraciones

Antes de migrar datos existentes, ejecutar el preflight de solo lectura en un entorno autorizado:

```bash
PYTHONPATH=src poetry run python scripts/audit_directory_integrity.py --host 127.0.0.1 --port 5435 --summary
```

No modifica settings ni datos. Incluye activos e inactivos, flags de estado y referencias históricas detectadas por FKs; `--summary` omite claves e IDs. Las únicas opciones CLI son `--summary`, `--host`, `--port`: no hay flags de reparación, actor o exclusión de inactivos. Un conflicto da salida `1` y bloquea la migración; resolver administrativamente sin borrar/fusionar automáticamente ni perder referencias de compras, ventas o cartera. Repetir el preflight tras la resolución autorizada.

Cadena del cambio: `e7a1b4c29d60` (unicidad Proveedor Persona, identificación normalizada, `lower(trim(username))` y nombre TipoCliente) -> `f8b2c5d30e71` (flags semánticos) -> `a9c3d6e41f82` (bootstrap de siete módulos y permisos). Aplicación y upgrade/downgrade requieren verificación separada; esta guía no certifica migraciones aplicadas ni pruebas PostgreSQL/E2E.

### Límites y deuda posterior

Consumidor Final sigue con `cliente_id=null`, sin registro falso. Cliente Sociedad no existe en este alcance: no se declara venta B2B completa. Persona/maestros comerciales son globales, no un directorio comercial aislado por tenant; solo Empleado valida su Empresa/contexto. Stock, referencias históricas, cartera y FE-EC no se modifican por este refactor.

Capacidades futuras propuestas para planificar en OpenSpec (no implementadas ni registradas por esta actualización documental): `customer-society` (Cliente jurídico y ventas B2B), `directory-company-enablement` (habilitación/visibilidad comercial por Empresa), `employee-multiemployment` (relaciones laborales múltiples), `customer-portal` (acceso externo delimitado), `foreign-identification-and-fiscal-plate` (identificación exterior/placa y reglas por comprobante). Su registro y priorización requieren cambios posteriores; esta documentación no cierra esa deuda.

---

## Matriz de Errores por Endpoint

| Endpoint                                   | Códigos esperados                 |
| ------------------------------------------ | --------------------------------- |
| `GET /api/v1/personas`                     | `200`, `422`                      |
| `GET /api/v1/personas/{id}`                | `200`, `404`                      |
| `POST /api/v1/personas`                    | `201`, `400`, `409`, `422`        |
| `PUT /api/v1/personas/{id}`                | `200`, `400`, `404`, `409`, `422` |
| `DELETE /api/v1/personas/{id}`             | `204`, `404`, `409`               |
| `GET /api/v1/tipos-cliente`                | `200`, `422`                      |
| `GET /api/v1/tipos-cliente/{id}`           | `200`, `404`                      |
| `POST /api/v1/tipos-cliente`               | `201`, `409`, `422`               |
| `PUT /api/v1/tipos-cliente/{id}`           | `200`, `404`, `409`, `422`        |
| `DELETE /api/v1/tipos-cliente/{id}`        | `204`, `404`, `409`               |
| `GET /api/v1/clientes`                     | `200`, `422`                      |
| `GET /api/v1/clientes/{id}`                | `200`, `404`                      |
| `POST /api/v1/clientes`                    | `201`, `404`, `409`, `422`        |
| `PUT /api/v1/clientes/{id}`                | `200`, `404`, `409`, `422`        |
| `DELETE /api/v1/clientes/{id}`             | `204`, `404`                      |
| `GET /api/v1/proveedores-persona`          | `200`, `422`                      |
| `GET /api/v1/proveedores-persona/{id}`     | `200`, `404`                      |
| `POST /api/v1/proveedores-persona`         | `201`, `400`, `404`, `409`, `422` |
| `PUT /api/v1/proveedores-persona/{id}`     | `200`, `400`, `404`, `409`, `422` |
| `DELETE /api/v1/proveedores-persona/{id}`  | `204`, `404`                      |
| `GET /api/v1/proveedores-sociedad`         | `200`, `422`                      |
| `GET /api/v1/proveedores-sociedad/{id}`    | `200`, `404`                      |
| `POST /api/v1/proveedores-sociedad`        | `201`, `400`, `404`, `409`, `422` |
| `PUT /api/v1/proveedores-sociedad/{id}`    | `200`, `400`, `404`, `409`, `422` |
| `DELETE /api/v1/proveedores-sociedad/{id}` | `204`, `404`                      |
| `GET /api/v1/empleados`                    | `200`, `422`                      |
| `GET /api/v1/empleados/{id}`               | `200`, `404`                      |
| `POST /api/v1/empleados`                   | `201`, `400`, `404`, `409`, `422` |
| `PUT /api/v1/empleados/{id}`               | `200`, `400`, `404`, `409`, `422` |
| `DELETE /api/v1/empleados/{id}`            | `204`, `404`                      |
