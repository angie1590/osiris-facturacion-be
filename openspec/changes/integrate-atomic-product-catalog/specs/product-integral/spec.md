## ADDED Requirements

### Requirement: Producto tendrá una única categoría principal autoritativa
El sistema MUST usar `Producto.categoria_principal_id` como única autoridad de clasificación de un producto activo. Durante transición, `tbl_producto_categoria` MUST ser una proyección con cero o una fila sincronizada por el servicio integral. La migración MUST backfillear solamente una relación legacy única y válida, sin elegir automáticamente entre relaciones ambiguas.

#### Scenario: Backfill de relación inequívoca
- **WHEN** un producto existente tiene exactamente una relación legacy con una categoría activa seleccionable
- **THEN** el backfill copia esa categoría al FK sin cambiar el ID del producto ni su relación proyectada

#### Scenario: Relación legacy ambigua
- **WHEN** un producto existente tiene cero o más de una relación legacy válida, o una categoría inválida
- **THEN** el preflight reporta el producto y las categorías candidatas legibles, el backfill no elige una categoría y el cutover queda bloqueado

#### Scenario: Alta activa sin categoría válida
- **WHEN** una solicitud crea un producto activo sin categoría principal o con categoría inactiva, padre o temporal
- **THEN** el servidor rechaza la solicitud y no persiste el producto ni sus relaciones

### Requirement: El preflight de Producto será de solo lectura y accionable
El sistema MUST ofrecer un preflight que reporte conflictos de clasificación, EAV y perfil tributario y, antes del cutover, divergencias FK/bridge; debe incluir IDs de producto, categorías candidatas y rutas legibles. Debe identificar obligatorios sin valor válido, valores activos no aplicables o duplicados, remapeos pendientes, resolver ambiguo, productos activos sin IVA, impuestos duplicados/inactivos/no permitidos y perfiles incompatibles. El preflight MUST NOT modificar registros ni seleccionar una categoría para resolver un conflicto.

#### Scenario: Preflight encuentra conflictos
- **WHEN** existen productos sin categoría, con varias categorías, categoría inválida o FK/bridge divergentes
- **THEN** el resultado indica que no es apto para migrar, enumera todos los conflictos accionables y la base permanece sin cambios

#### Scenario: Preflight sin conflictos
- **WHEN** todos los productos cumplen los criterios de backfill y consistencia
- **THEN** el resultado indica aptitud, reporta conteos y no altera datos

#### Scenario: Preflight encuentra conflictos de EAV o impuestos
- **WHEN** un producto activo tiene un obligatorio faltante, EAV no aplicable/duplicado o perfil tributario inválido
- **THEN** el resultado informa el producto, código de conflicto y atributo/impuesto afectado, sin modificar datos

### Requirement: Alta de Producto será integral y atómica
`POST /api/v1/productos` MUST validar en una transacción exterior una categoría principal seleccionable, atributos efectivos, valores/defaults explícitos, perfil tributario permitido y relaciones requeridas; MUST persistir Producto, FK/proyección bridge temporal, impuestos, EAV y auditoría con un único commit. Cualquier fallo MUST revertir todas las escrituras. La identidad del actor MUST provenir del contexto autenticado.

#### Scenario: Alta integral válida
- **WHEN** un actor autorizado envía datos generales, categoría válida, perfil tributario válido y todos los atributos obligatorios explícitos o satisfechos por defaults configurados
- **THEN** la API responde con el detalle canónico y persiste todas las relaciones y eventos de auditoría en una transacción

#### Scenario: Alta con atributo obligatorio faltante
- **WHEN** falta un atributo obligatorio y la configuración efectiva no tiene default explícito válido
- **THEN** la API responde `422 PRODUCT_REQUIRED_ATTRIBUTES_MISSING` con campos faltantes y revierte producto, bridge, impuestos, EAV y auditoría

#### Scenario: Falla una escritura posterior a crear Producto
- **WHEN** falla la persistencia de impuestos, EAV, proyección o auditoría durante el alta
- **THEN** la transacción completa se revierte y no queda ningún registro parcial

### Requirement: Todo Producto activo estará completo al finalizar el cutover
Después del cutover, el sistema MUST impedir que un producto activo quede sin categoría principal activa seleccionable, perfil tributario válido o valor tipado para cada atributo efectivo obligatorio. La comprobación de categoría/jerarquía MUST ejecutarse bajo el lock de jerarquía; la migración inicial MUST mantener la columna nullable y no activar la restricción final hasta que el postflight confirme todos los productos activos.

#### Scenario: Postflight habilita la restricción
- **WHEN** el postflight confirma que todos los productos activos tienen categoría válida, perfil tributario y atributos obligatorios válidos
- **THEN** el cutover puede activar la restricción final sin alterar registros históricos inactivos

#### Scenario: Producto existente incompleto bloquea cutover
- **WHEN** el postflight encuentra un producto activo sin categoría, impuesto permitido o valor obligatorio
- **THEN** reporta IDs y campos faltantes y mantiene desactivada la restricción final hasta reconciliación explícita

### Requirement: Edición integral preservará la semántica de valores EAV
`PUT /api/v1/productos/{id}` MUST actualizar los datos generales, categoría, perfil tributario y EAV bajo una transacción exterior. Sin cambio de categoría, los EAV omitidos MUST conservarse; `null` MUST desactivar solo valores opcionales y MUST rechazarse para obligatorios. Un cambio de categoría MUST conservar valores compartidos válidos por `atributo_id`, desactivar lógicamente los que dejan de aplicar y conservar su historia.

#### Scenario: Edición ordinaria conserva valores omitidos
- **WHEN** una edición no cambia categoría y omite un atributo ya persistido
- **THEN** el valor existente permanece activo y las modificaciones solicitadas se confirman junto con impuestos y auditoría

#### Scenario: Intento de limpiar un obligatorio
- **WHEN** una edición envía `null` para un atributo efectivo obligatorio
- **THEN** la API devuelve `422 PRODUCT_REQUIRED_ATTRIBUTES_MISSING` y no cambia ninguna parte del producto

#### Scenario: Cambio de categoría conserva y desactiva
- **WHEN** se confirma un cambio de categoría autorizado con preview vigente
- **THEN** los atributos compartidos y válidos permanecen activos, los no aplicables se desactivan sin borrar historia y los nuevos obligatorios quedan satisfechos

### Requirement: Cambio de categoría requerirá preview ligado al estado
El sistema MUST ofrecer `POST /api/v1/productos/{id}/previsualizar-cambio-categoria` y MUST firmar la operación, actor, producto, categoría destino, payload relevante, estado del catálogo/producto y expiración. La confirmación integral MUST validar el token bajo locks y volver a resolver aplicabilidad. El preview MUST identificar valores conservados, desactivados, defaults explícitos, nuevos obligatorios y faltantes.

#### Scenario: Preview informa el impacto completo
- **WHEN** se solicita cambiar la categoría de un producto existente
- **THEN** la API responde con el resumen, conteos y detalle de valores conservados/desactivados/defaults/faltantes sin persistir cambios

#### Scenario: Preview obsoleto
- **WHEN** cambia el producto, categoría, asignación, atributo, actor, destino o payload después del preview
- **THEN** la confirmación devuelve `409 CATALOG_PREVIEW_STALE` y no altera producto, EAV, impuestos ni auditoría

#### Scenario: Cambio sin token requerido
- **WHEN** una edición cambia categoría sin token vigente
- **THEN** la API responde `409 PRODUCT_CATEGORY_CHANGE_REQUIRES_PREVIEW` sin persistir cambios

### Requirement: Producto usará autorización efectiva y auditoría autenticada
Las rutas canónicas MUST autorizar lectura con `PRODUCTOS.leer`, alta con `PRODUCTOS.crear`, edición y preview con `PRODUCTOS.actualizar`, y baja con `PRODUCTOS.eliminar`. La API MUST ignorar o rechazar `usuario_auditoria` como identidad y registrar el actor autenticado. Los eventos integrales MUST confirmarse o revertirse con el cambio de negocio.

#### Scenario: Usuario sin permiso efectivo
- **WHEN** un usuario autenticado sin el permiso efectivo requerido invoca una operación de Producto
- **THEN** la API responde `403` y no persiste cambios

#### Scenario: Actor no confiable enviado por cliente
- **WHEN** el payload incluye `usuario_auditoria` diferente del usuario autenticado
- **THEN** el servidor no usa ese valor como actor y registra la identidad autenticada

### Requirement: Detalle de Producto será canónico y los errores críticos serán visibles
La lectura completa MUST exponer categoría principal con ruta, atributos efectivos identificados por UUID con valor tipado, unidad/origen/metadatos pertinentes, perfil tributario y datos de bodega requeridos por el contrato. Errores críticos de categoría, EAV o impuestos MUST producir un error explícito; MUST NOT convertirse en listas vacías que parezcan válidas.

#### Scenario: Lectura completa consistente
- **WHEN** se solicita el detalle de un producto válido
- **THEN** la respuesta contiene datos generales, categoría principal legible, atributos efectivos con valores/unidades, impuestos y bodegas según contrato

#### Scenario: Falla el resolver de atributos
- **WHEN** el resolver efectivo falla por ambigüedad o error de integridad
- **THEN** la lectura responde con error diagnóstico y no presenta `atributos: []` como si el producto no tuviera atributos

### Requirement: Los errores de Producto tendrán códigos y campos estables
Las rutas canónicas MUST responder con `code` y `message`; los errores de validación por atributo MUST identificar campos en `fields` y, cuando corresponda, incluir `conteos` y `acciones_permitidas`. El servidor MUST distinguir categoría requerida/inválida/no seleccionable, conflicto FK/bridge, categoría legacy ambigua, atributo no aplicable/valor inválido, obligatorio faltante, preview requerido/obsoleto, perfil tributario inválido y estado concurrente del producto mediante los códigos canónicos definidos por esta entrega.

#### Scenario: Categoría o atributo inválido
- **WHEN** la solicitud omite categoría, usa una categoría no seleccionable o envía un atributo no aplicable/valor fuera de tipo o rango
- **THEN** la API devuelve respectivamente `PRODUCT_CATEGORY_REQUIRED`, `PRODUCT_CATEGORY_NOT_SELECTABLE`, `PRODUCT_ATTRIBUTE_NOT_APPLICABLE` o `PRODUCT_ATTRIBUTE_VALUE_INVALID` con HTTP 422/409 según el contrato y sin escrituras

#### Scenario: Perfil tributario inválido
- **WHEN** la solicitud contiene impuestos inactivos, incompatibles o no permitidos para el perfil empresarial resuelto
- **THEN** la API devuelve `422 PRODUCT_TAX_PROFILE_INVALID` y revierte todos los cambios
