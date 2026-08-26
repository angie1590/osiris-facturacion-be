---
id: procesos-maestros-comerciales-directorio
title: "02. Maestros Comerciales y Directorio"
sidebar_position: 3
---

# 02. Maestros Comerciales y Directorio

## CU010: Registrar personas (base única)

**Actores:** Administrador, Asistente Administrativo.

**Descripción:** Registrar personas naturales para ser reutilizadas como clientes, empleados o proveedores persona.

**Precondiciones:**

- Usuario autenticado con permisos sobre directorio.

**Flujo de Eventos Básico:**

1. El actor abre formulario de persona.
2. Ingresa identificación, nombres y datos de contacto.
3. Guarda registro.
4. El sistema lo deja disponible para otros módulos.

**Flujos Alternativos:**

- Identificación duplicada: el sistema rechaza.

**Postcondiciones:**

- Persona activa y reutilizable transversalmente.

**APIs involucradas:**

- `POST /api/v1/personas` ([doc API](../api/common/directorio))
- `GET /api/v1/personas` ([doc API](../api/common/directorio))

---

## CU011: Registrar clientes

**Actores:** Administrador, Asistente de Ventas.

**Descripción:** Dar de alta clientes para facturación y cartera.

**Precondiciones:**

- Persona o datos del cliente disponibles según tipo.

**Flujo de Eventos Básico:**

1. El actor ingresa a clientes.
2. Selecciona nuevo cliente.
3. Completa datos comerciales/tributarios.
4. Guarda y valida disponibilidad en ventas.

**Flujos Alternativos:**

- Datos de identificación inválidos: no permite guardar.

**Postcondiciones:**

- Cliente activo para usar en ventas y reportería.

**APIs involucradas:**

- `POST /api/v1/clientes` ([doc API](../api/common/directorio))
- `GET /api/v1/clientes` ([doc API](../api/common/directorio))

---

## CU012: Registrar proveedores (persona o sociedad)

**Actores:** Administrador, Asistente de Compras.

**Descripción:** Crear proveedores para compras y retenciones emitidas.

**Precondiciones:**

- Para proveedor persona: persona existente o datos completos.
- Para proveedor sociedad: RUC y razón social válidos.

**Flujo de Eventos Básico:**

1. Definir tipo de proveedor (persona/sociedad).
2. Registrar proveedor con datos fiscales.
3. Validar disponibilidad en módulo compras.

**Flujos Alternativos:**

- Duplicidad de identificación/RUC: operación rechazada.

**Postcondiciones:**

- Proveedor activo para registrar compras.

**APIs involucradas:**

- `POST /api/v1/proveedores-persona` ([doc API](../api/common/directorio))
- `POST /api/v1/proveedores-sociedad` ([doc API](../api/common/directorio))

---

## CU013: Registrar empleados operativos

**Actores:** Administrador, RRHH.

**Descripción:** Dar de alta empleados para operación interna y trazabilidad.

**Precondiciones:**

- Persona existente.
- Empresa activa.

**Flujo de Eventos Básico:**

1. Registrar empleado con datos laborales.
2. Asociar empresa.
3. Verificar en listados activos.

**Flujos Alternativos:**

- Persona no válida o empresa no disponible: rechazo de registro.

**Postcondiciones:**

- Empleado activo en directorio interno.

**APIs involucradas:**

- `POST /api/v1/empleados` ([doc API](../api/common/directorio))
- `GET /api/v1/empleados` ([doc API](../api/common/directorio))

