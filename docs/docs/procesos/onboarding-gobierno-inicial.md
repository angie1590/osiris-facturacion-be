---
id: procesos-onboarding-gobierno-inicial
title: "01. Onboarding y Gobierno Inicial"
sidebar_position: 2
---

# 01. Onboarding y Gobierno Inicial

## CU001: Registrar empresa y parámetros tributarios base

**Actores:** Administrador del sistema.

**Descripción:** Crear la entidad jurídica (RUC) y dejar lista la configuración base para operar emisión y transacciones.

**Precondiciones:**

- Usuario autenticado con permisos de administración.
- Definición previa de régimen tributario y modo de emisión.

**Flujo de Eventos Básico:**

1. El actor abre módulo de onboarding empresarial.
2. Registra datos fiscales y comerciales de empresa.
3. Guarda la empresa en el sistema.
4. El sistema crea automáticamente la sucursal matriz (`codigo=001`, `es_matriz=true`).

**Flujos Alternativos:**

- Si el RUC ya existe, el sistema rechaza el registro.
- Si la combinación régimen/modo de emisión es inválida, el sistema responde con error de validación.

**Postcondiciones:**

- Empresa creada y activa.
- Sucursal matriz disponible para configurar puntos de emisión.

**APIs involucradas:**

- `POST /api/v1/empresas` ([doc API](../api/common/onboarding))
- `GET /api/v1/empresas` ([doc API](../api/common/onboarding))

---

## CU002: Configurar sucursales y puntos de emisión

**Actores:** Administrador, Responsable Operativo.

**Descripción:** Completar estructura operativa SRI: sucursales y puntos de emisión.

**Precondiciones:**

- Empresa activa.
- Sucursal matriz existente.

**Flujo de Eventos Básico:**

1. El actor registra sucursales adicionales cuando aplica.
2. Para cada sucursal, registra uno o varios puntos de emisión.
3. Verifica que códigos de establecimiento y punto sean únicos por su ámbito.

**Flujos Alternativos:**

- Si se repite código de sucursal en la misma empresa, el sistema rechaza.
- Si se intenta crear punto sin sucursal válida/activa, el sistema rechaza.

**Postcondiciones:**

- Estructura Empresa -> Sucursal -> Punto de Emisión completa.

**APIs involucradas:**

- `POST /api/v1/sucursales` ([doc API](../api/common/onboarding))
- `POST /api/v1/puntos-emision` ([doc API](../api/common/onboarding))

---

## CU003: Gestionar secuenciales SRI por punto de emisión

**Actores:** Administrador, Supervisor de Facturación.

**Descripción:** Gestionar secuenciales con control transaccional y formato SRI.

**Precondiciones:**

- Punto de emisión activo.
- Tipo de documento definido (factura, retención, etc.).

**Flujo de Eventos Básico:**

1. El actor consulta/solicita siguiente secuencial por tipo documental.
2. El sistema retorna secuencial en formato 9 dígitos.
3. Para ajustes manuales, actor autorizado registra motivo y nuevo valor.

**Flujos Alternativos:**

- Ajuste sin permisos adecuados: operación denegada y auditada.

**Postcondiciones:**

- Secuenciales controlados y trazables.

**APIs involucradas:**

- `POST /api/v1/puntos-emision/{punto_emision_id}/secuenciales/{tipo_documento}/siguiente` ([doc API](../api/common/onboarding))
- `POST /api/v1/puntos-emision/{punto_emision_id}/secuenciales/{tipo_documento}/ajuste-manual` ([doc API](../api/common/onboarding))

---

## CU004: Alta de roles, usuarios y permisos

**Actores:** Administrador de Seguridad.

**Descripción:** Configurar acceso al ERP por rol y permisos de módulo.

**Precondiciones:**

- Persona registrada para cada usuario.
- Rol activo con permisos definidos.

**Flujo de Eventos Básico:**

1. Crear/ajustar roles.
2. Asignar permisos por módulo al rol.
3. Registrar usuario y vincular rol.
4. Verificar menú/permisos efectivos del usuario.

**Flujos Alternativos:**

- Username duplicado o persona ya vinculada: creación rechazada.

**Postcondiciones:**

- Usuarios listos para operar con permisos correctos.

**APIs involucradas:**

- `POST /api/v1/roles` ([doc API](../api/common/seguridad-accesos))
- `POST /api/v1/roles-modulos-permisos` ([doc API](../api/common/seguridad-accesos))
- `POST /api/v1/usuarios` ([doc API](../api/common/seguridad-accesos))
- `GET /api/v1/usuarios/{usuario_id}/menu` ([doc API](../api/common/seguridad-accesos))

---

## CU005: Seleccionar empresa activa de sesión

**Actores:** Todos los usuarios operativos.

**Descripción:** Definir empresa activa en sesión para aislar datos y procesos.

**Precondiciones:**

- Usuario autenticado.
- Empresa habilitada para el usuario.

**Flujo de Eventos Básico:**

1. El usuario selecciona empresa al iniciar sesión.
2. Frontend actualiza token/contexto con `empresa_id`.
3. Todas las operaciones posteriores se ejecutan sobre esa empresa.

**Flujos Alternativos:**

- Si el frontend intenta operar otra empresa, backend retorna `403`.

**Postcondiciones:**

- Operación multiempresa aislada por sesión.

**APIs involucradas:**

- Contrato de sesión multiempresa ([doc API](../api/common/empresa-seleccionada-sesion))

