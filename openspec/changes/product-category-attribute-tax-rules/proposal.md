## Why

El dominio de catálogo ya tiene partes de las reglas —categorías jerárquicas, atributos tipados, productos `BIEN/SERVICIO` y un catálogo tributario por empresa—, pero API y frontend no forman un contrato coherente. En particular, el producto no está asociado a la configuración tributaria de la empresa: la ruta visible solo envía un impuesto, el alta permite omitir la lista vacía, la edición no actualiza asignaciones y ventas/compras leen relaciones globales.

Este cambio convierte las reglas adjuntas en un contrato ejecutable para categorías, atributos y productos, adaptado al esquema multiempresa de facturación.

## What Changes

- Normalizar al español todas las rutas del frontend. Consolidar la administración de productos en un flujo canónico `/productos`; las rutas inglesas heredadas redirigirán a la ruta española y no servirán páginas duplicadas.
- Formalizar jerarquía, movimiento, baja lógica y categorías temporales: al convertir una categoría poblada en padre, crear su hija `Sin clasificar` al mismo nivel que la nueva subcategoría, mover los productos directos y obligar a completar su recategorización con una alerta global persistente.
- Completar atributos heredados con tipos `select` y `catalog`, opciones/valores válidos, obligatoriedad y remapeo tipado; limitar nombres duplicados a la misma rama, no globalmente.
- Mantener `BIEN/SERVICIO` como dato de producto y validar su compatibilidad al crear, editar y asignar tributos.
- Si una empresa guarda su configuración sin haber elegido IVA, incluir automáticamente el IVA 0% vigente del catálogo. Los productos deben tener un IVA y pueden tener además ICE; solo estos dos tipos de impuesto forman parte del perfil tributario de producto.
- Hacer que cada perfil tributario de producto use únicamente impuestos activos, vigentes y configurados para la empresa, con selección múltiple y máximo de una asignación activa por tipo.
- Asociar asignaciones tributarias con empresa, dado que un producto puede vincularse a bodegas de varias empresas; actualizar snapshots de compras y ventas para resolver los impuestos de la empresa operada.
- Migrar las asignaciones globales actuales de forma auditable; reportar y bloquear filas cuya empresa no pueda determinarse sin inventar una configuración.
- Preservar auditoría, permisos, rechazo de stock según el tipo de producto y snapshots históricos de documentos.
- Conservar los defaults tipados actuales para atributos obligatorios.

## Capabilities

### New Capabilities
- `product-category-attribute-tax-rules`: ciclo de vida de categorías y atributos, catálogo de productos `BIEN/SERVICIO` y asignaciones tributarias múltiples acotadas por empresa.

### Modified Capabilities
- Ninguna. No hay especificaciones principales en `openspec/specs/`; el contrato nuevo se incorporará mediante una capacidad nueva y su delta en este cambio.

## Impact

- Backend: `inventario/categoria`, `atributo`, `categoria_atributo`, `producto`, `producto_impuesto`, `sri/impuesto_catalogo` y validación de alcance empresarial.
- Integraciones: resolución de impuestos y snapshots en compras, ventas y documentos electrónicos; no cambiar reglas de cálculo ni XML fuera de los códigos/tarifas seleccionados.
- Datos: nuevas restricciones/campos y revisión Alembic de asignaciones existentes; posible conciliación manual antes de migrar registros huérfanos.
- Frontend: ruta canónica de productos, formulario, selector tributario filtrado por empresa, edición y asignación de atributos.
- Seguridad: categoría/atributos con roles de administración; productos según matriz RBAC vigente; no confiar en filtros enviados solo por el navegador.
