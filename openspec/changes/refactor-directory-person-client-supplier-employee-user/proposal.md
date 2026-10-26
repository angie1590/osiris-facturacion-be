## Why

El Directorio debe mantener una sola identidad natural reutilizable y garantizar integridad, trazabilidad y revocacion de acceso. El documento `OSIRIS_FACTURACION_MODULO_PERSONAS_REGLAS_NEGOCIO_OPENSPEC.md` (revision declarada 2026-10-02) es la fuente funcional; sus hallazgos se contrastaran con el codigo y la base actual antes de migrar, sin asumir que el commit revisado sigue siendo el vigente.

## What Changes

- Consolidar Persona como identidad natural global y Cliente, Proveedor Persona, Empleado y Usuario como roles unicos por composicion, no herencia ORM.
- Incorporar busqueda exacta normalizada, vinculos/dependencias y reactivacion explicita; bloquear baja de Persona y TipoCliente con dependencias activas.
- Extender altas existentes con una alternativa excluyente `persona_id` o `persona_nueva`; para sociedades, `persona_contacto_id` o `persona_contacto_nueva`. Resolver y persistir cada operacion en una transaccion, incluyendo carreras por identificacion.
- Garantizar unicidad real de roles, RUC e identificacion y username case-insensitive mediante Alembic y preflight de duplicados sin fusion automatica.
- **BREAKING**: rechazar cambios de identidad antes ignorados; exigir contrasenas de ocho o mas caracteres en todas las operaciones de escritura de credenciales.
- Permitir cambio auditado de contacto de sociedad, incluyendo contacto nuevo en una operacion atomica.
- Desactivar Empleado y Usuario asociado e invalidar sesiones en la misma transaccion; reactivar Empleado no restaura acceso automaticamente.
- Verificar auditoria derivada de autenticacion, RBAC autoritativo, FKs activas, politica tributaria aislada y metadatos semanticos de TipoContribuyente.
- Coordinar con el cambio frontend del mismo nombre: todas las interfaces usan exclusivamente componentes comunes existentes o nuevos compartidos; no se implementa UI en este repositorio.

## Capabilities

### New Capabilities

- `directory-party-roles`: identidad natural, roles, proveedores juridicos, catalogos, consultas, ciclo de vida, operaciones compuestas, seguridad e integridad del Directorio.

### Modified Capabilities

Ninguna spec principal existente: `openspec/specs` esta vacio. No modificar los artefactos de otros cambios, incluido `establish-ecuador-product-domain`; contrastar sus contratos de acceso/ventas/compras durante implementacion.

## Impact

- Backend: `src/osiris/modules/common/{persona,tipo_cliente,cliente,proveedor_persona,proveedor_sociedad,empleado,usuario,tipo_contribuyente}`, servicios/repositorios base, validadores, autenticacion, contexto de auditoria, RBAC, migraciones y pruebas existentes.
- API: conservar `/api/v1/personas`, `/tipos-cliente`, `/clientes`, `/proveedores-persona`, `/proveedores-sociedad`, `/empleados`, `/usuarios`, `/roles`, `/roles-modulos-permisos` y `/auth/*`; sumar consultas y acciones de dominio. No exponer hashes ni aceptar actor falsificado.
- Inventario: sin cambios de stock, costos, reservas ni movimientos. Cartera: conservar referencias historicas a clientes/proveedores, sin recalcular saldos. SRI: separar validacion local de existencia/estado tributario; no alterar emision ni la rueda FE-EC. Consumidor Final sigue con `cliente_id=null`.
- Multiempresa: Persona y maestros comerciales siguen globales; Empleado valida Empresa y permisos de tenant. No declarar aislamiento comercial completo sin relaciones de habilitacion por empresa.
- No objetivos: Cliente Sociedad, identificacion del exterior, placa fiscal, multiempleo, portal de clientes y habilitacion comercial por empresa. Registrar esos cambios futuros, especialmente Cliente Sociedad antes de declarar ventas B2B completas.
- Entrega: solo planificacion en este cambio inicial; implementar backend por fases antes de habilitar consumidores frontend dependientes. La validacion OpenSpec no certifica aun datos reales ni comportamiento de aplicacion.