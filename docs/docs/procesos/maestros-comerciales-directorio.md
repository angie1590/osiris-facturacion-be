---
id: procesos-maestros-comerciales-directorio
title: "02. Maestros Comerciales y Directorio"
sidebar_position: 3
---

# 02. Maestros Comerciales y Directorio

Persona es una identidad natural global. Cliente, Proveedor Persona, Empleado y Usuario son composiciones 1:1 por FK única; Sociedad mantiene identidad jurídica propia y contacto natural mutable 1:N. Seleccionar Empresa no aísla estos maestros comerciales; Empleado sí valida Empresa/contexto autorizado. Cliente Sociedad, habilitación comercial por Empresa, multiempleo, portal e identificación exterior/placa fiscal son deuda posterior, no prestaciones terminadas.

## Reglas Comunes de Alta y Ciclo de Vida

Search-or-Create busca identificación exacta incluyendo inactivos. Reutiliza Persona activa sin sobrescribir; la nueva permanece como borrador en el formulario padre. Completar o cancelar Persona no guarda ni borra datos laborales/comerciales del padre. Al guardar se envía una sola petición del rol con `persona_id` XOR `persona_nueva` (Sociedad: `persona_contacto_id` XOR `persona_contacto_nueva`). Ambas/ninguna en alta producen `422`. No crear Persona con una petición previa para estos recorridos.

El backend resuelve identidad y rol en una unidad de trabajo, con commit exterior y rollback completo. Una carrera por identificación puede reutilizar la Persona ganadora activa sin sobrescribirla; duplicar rol o encontrar inactivo devuelve `409`. La reactivación es una acción POST autorizada sobre el mismo ID, no un alta duplicada ni PUT `activo=true`.

Cada entidad usa su permiso efectivo propio: `PERSONAS`, `TIPOS_CLIENTE`, `CLIENTES`, `PROVEEDORES_PERSONA`, `PROVEEDORES_SOCIEDAD`, `EMPLEADOS`, `USUARIOS`. Además de crear el rol se exige `PERSONAS.leer`; insertar Persona requiere `PERSONAS.crear`, y alta Empleado requiere `USUARIOS.crear`. El nombre del actor funcional no concede permisos. El JWT determina auditoría; no enviar `usuario_auditoria` en formularios productivos.

Consultar `GET /api/v1/personas/{id}/vinculos` antes de baja; el backend vuelve a validar dependencias. Baja Persona/TipoCliente bloqueada devuelve `409`. Consultar activos por defecto, todos con `only_active=false` y solo inactivos con `estado=inactivo`. Búsqueda, orden y total son de servidor. Detalles de contrato, proyecciones Read y errores: [Directorio API](../api/common/directorio).

## CU010: Registrar personas (base única)

**Actores:** Administrador, Asistente Administrativo.

**Descripción:** Registrar personas naturales para ser reutilizadas como clientes, empleados o proveedores persona.

**Precondiciones:**

- Usuario autenticado con `PERSONAS.crear`; lectura y reactivación requieren permisos propios.

**Flujo de Eventos Básico:**

1. El actor abre formulario de persona.
2. Ingresa identificación, nombres y datos de contacto. Cédula/RUC natural se validan localmente; pasaporte se normaliza a mayúsculas y exige mínimo cinco caracteres.
3. Guarda registro.
4. El sistema lo deja disponible para otros módulos.

**Flujos Alternativos:**

- Alta independiente con identificación duplicada: rechazo; en alta contextual del rol se reutiliza la Persona activa sin sobrescribir.
- Persona inactiva: consultar y reactivar explícitamente con permiso, no crear otra identidad.
- Validación local no certifica existencia/actividad SRI ni autorización del comprobante.

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

- Persona natural activa o borrador y TipoCliente activo; permisos de alta y composición.

**Flujo de Eventos Básico:**

1. El actor ingresa a clientes.
2. Selecciona nuevo cliente.
3. Busca/selecciona Persona o completa su borrador; selecciona TipoCliente activo (descuento decimal 0..100).
4. Guarda con un único POST Cliente y valida disponibilidad en ventas. Consumidor Final conserva `cliente_id=null`, sin Cliente/Persona ficticio.

**Flujos Alternativos:**

- Datos de identificación inválidos: no permite guardar.
- Cliente activo/inactivo ya asociado: `409`; consultar o reactivar explícitamente. Cambio de `persona_id`: `409`; cambio de TipoCliente activo permitido.
- Cliente Sociedad no está implementado; no afirmar ventas B2B completas.

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

- Para proveedor persona: Persona con RUC natural y catálogo activo con `aplica_persona_natural=true`.
- Para proveedor sociedad: RUC jurídico, razón social, dirección, email obligatorio, teléfono opcional y contacto natural activo/nuevo; catálogo con `aplica_sociedad=true`.

**Flujo de Eventos Básico:**

1. Definir tipo de proveedor (persona/sociedad).
2. Buscar o preparar Persona/contacto sin persistirlo aparte; registrar proveedor y borrador en una petición compuesta.
3. Validar disponibilidad en módulo compras.

**Flujos Alternativos:**

- Duplicidad de identificación/RUC: operación rechazada.
- Identidad natural activa encontrada en alta contextual: reutilización sin sobrescritura; rol/RUC duplicado o inactivo: `409` con acción explícita.
- Sociedad permite cambiar contacto por existente/nuevo en PUT atómico; omitir ambas alternativas conserva contacto. No modifica Persona anterior.
- Flags aprobados: `01`/`03` natural, `02`/`05` sociedad, `04` ambos, desconocido ninguno. No inferir por nombre ni afirmar validez tributaria por formato local.

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

- Persona activa existente o borrador natural.
- Empresa activa/autorizada, Rol activo y bloque `usuario` obligatorio; permisos `EMPLEADOS.crear`, `USUARIOS.crear` y composición Persona.

**Flujo de Eventos Básico:**

1. Buscar Persona o completar borrador y datos laborales: salario decimal no negativo, ingreso no futuro, salida posterior y edad mínima configurable (default 16).
2. Asociar Empresa y acceso (`username`, Rol, contraseña de ocho o más caracteres).
3. Guardar Persona+Empleado+Usuario con un commit exterior; verificar en listados activos, sin credenciales en Read.

**Flujos Alternativos:**

- Persona no válida o empresa no disponible: rechazo de registro.
- Usuario previo para Persona: `409`, decisión administrativa sin duplicar cuenta ni sobrescribir credenciales; fallo de cualquier parte revierte todo.
- Empleado conserva unicidad global por Persona; no habilita multiempleo. Cambio efectivo de `persona_id`: `409`.

**Postcondiciones:**

- Empleado y Usuario activos con Persona compartida; alta marca cambio obligatorio de contraseña.
- Baja Empleado desactiva Usuario asociado e invalida access/refresh en la misma transacción, sin bajar Persona/Cliente/proveedores.
- Reactivar Empleado conserva ID y no restaura Usuario. Reactivar Usuario exige acción administrativa separada; si Empleado sigue inactivo, requiere `confirmar_empleado_inactivo=true` explícito.

**APIs involucradas:**

- `POST /api/v1/empleados` ([doc API](../api/common/directorio))
- `GET /api/v1/empleados` ([doc API](../api/common/directorio))
