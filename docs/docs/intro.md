---
sidebar_position: 1
---

# Osiris ERP

Osiris es un ERP para PYMES en Ecuador, diseñado para operar procesos de inventario, ventas, compras, cartera y reportes, con soporte de cumplimiento fiscal del SRI (Servicio de Rentas Internas).

En términos de plataforma, Osiris expone una API backend (FastAPI + SQLModel/SQLAlchemy) y define reglas de negocio transversales para catálogos, transacciones y trazabilidad.

:::info Alcance de esta documentación
Esta guía oficial cubre fundamentos, setup local, workflow de desarrollo, arquitectura core y modelo de datos de alto nivel.
:::

:::warning Contexto fiscal
Las reglas SRI evolucionan en el tiempo; valida siempre la parametrización vigente en tu entorno (`.env.development`) y catálogos tributarios antes de desplegar cambios.
:::

## Glosario estricto

### Empresa

Entidad jurídica principal. Define régimen tributario y modo de emisión permitido.

### Sucursal

Unidad operativa de una Empresa. Agrupa operación física/administrativa.

### Punto de emisión

Configuración documental asociada a una Sucursal para secuenciales y emisión de comprobantes.

### Rol

Perfil de autorización funcional (RBAC). Determina permisos sobre módulos y acciones sensibles.

### Usuario

Cuenta autenticable del sistema. Se asocia a Persona y Rol para seguridad y auditoría.

### Persona

Identidad exclusivamente natural y global. Cliente, Proveedor Persona, Empleado y Usuario se componen mediante una FK `persona_id` única por rol (1:1), sin herencia ORM ni copia de identidad. Una misma Persona puede reunir varios roles. Proveedor Sociedad conserva su identidad jurídica separada y un contacto natural mutable; una Persona puede contactar varias sociedades (1:N).

### Cliente

Contraparte natural para ventas y CxC. Cliente Sociedad sigue pendiente: no se declara cobertura B2B completa. Consumidor Final usa `cliente_id=null`, sin crear una Persona o Cliente ficticios.

### Proveedor

Contraparte comercial para compras y CxP (implementado por dominios de proveedor persona/sociedad).

### Facturación electrónica

Flujo de emisión con documentos electrónicos, cola SRI, autorización y artefactos XML/RIDE.

### Facturación física

Emisión de `NOTA_VENTA_FISICA`; restringida por reglas tributarias del régimen emisor.

### RIMPE Negocio Popular

Régimen tributario con reglas específicas de emisión. `NOTA_VENTA_FISICA` solo aplica aquí.

### Venta

Transacción comercial de salida con detalle, impuestos, estado y efecto en CxC/inventario.

### Compra

Transacción comercial de entrada con detalle, impuestos, estado y efecto en CxP/inventario.

### CxC (Cuenta por cobrar)

Estado financiero de deuda de clientes asociada a ventas.

### CxP (Cuenta por pagar)

Estado financiero de deuda con proveedores asociada a compras.

### Retención emitida

Documento tributario sobre compras/cuentas por pagar.

### Retención recibida

Documento tributario recibido en contexto de ventas/cuentas por cobrar.

### Catálogos base

Conjunto de maestros de referencia del sistema (organizacionales, inventario y tributarios) consumidos por las transacciones.

### Categoría hoja

Nodo terminal del árbol de categorías. Los productos deben vincularse a categorías hoja.

### EAV

Modelo Entidad-Atributo-Valor para catálogo dinámico de atributos de producto.

### Soft delete

Borrado lógico (`activo = false`) para preservar trazabilidad y relaciones.

El Directorio y sus maestros comerciales son globales; seleccionar Empresa no ofrece aislamiento comercial completo. Empleado valida su Empresa y acceso autorizado, pero mantiene unicidad global por Persona. Habilitación comercial por empresa, multiempleo, portal, identificación del exterior y placa fiscal requieren cambios posteriores.

### Auditoría

Registro de cambios y acciones sensibles para trazabilidad operativa y de seguridad.

:::info Cobertura de dominio
Osiris no se modela solo como `Empresa > Sucursal > Punto de emisión`. Esa es una dimensión organizacional; el ERP completo integra además seguridad (roles/usuarios/personas), maestros de negocio (clientes/proveedores/producto/catálogos) y transacciones (ventas, compras, cartera, retenciones, facturación electrónica/física).
:::
