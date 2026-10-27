## Context

Fuente funcional: documento Osiris Categorias, Atributos y Unidades de Atributo v2.0, 2026-10-25, mas los cuatro ajustes aceptados en conversacion. Bases auditadas: backend `768f6a1aeeb8e621f2219bb8cd315877cf8e5025`, frontend `1325129a90523b0a0ed8fdcd5d2c842cdd33331b`.

Par coordinado: `osiris-facturacion-fe/openspec/changes/close-catalog-attribute-units`. Este archivo contiene decisiones completas para el alcance actual sin depender del archivo externo del Desktop. Propuesta/specs/tareas son planificacion: ninguna tarea de implementacion se considera ejecutada.

Estado reutilizable: CTE de ancestros, EAV tipado, B3, auditoria, snapshot AtributoCambio y rutas de preview/reversion. Brechas: es_padre enviado por cliente, backfill implicito/defaults artificiales, unicidad solo activa de asignaciones, herencia reconstruida en UI y ausencia de Unidad/codigo. Producto aun utiliza puente y requests separados; no se corrige su formulario en esta fase.

## Goals / Non-Goals

**Goals:** entregas verticales 1-6, catalogo global, jerarquia derivada, identidad historica, resolver unico, configuracion local separada de definicion global, defaults explicitos, unidades numericas, anotacion confirmada y restauracion segura.

**Non-Goals:** implementar entregas 7-8, agregar unidad comercial, conversiones, variantes, empaques, remediacion persistente, inferir datos, fusionar duplicados, alterar stock/cartera/SRI/documentos historicos, ejecutar migraciones o preflight real durante esta propuesta.

## Decisions

### 1. Secuencia y ownership

Entregas BE y FE comparten IDs 1-6 y gates. Cada una exige API, permisos efectivos, auditoria, pruebas y documentacion, mas UI administrativa correspondiente. `manage-reversible-attribute-lifecycle` es antecedente y se reutiliza; no se archiva, no se modifican sus checkboxes y no se duplica la tabla snapshot. Esta propuesta toma ownership de defaults opt-in/unidades y de la evidencia pendiente relacionada con legacy, rollback y PostgreSQL. El cierre conjunto debe conciliar evidencia antes de archivar cualquiera de los cambios.

### 2. Categoria principal: expandir sin activar Producto

Destino aprobado: `Producto.categoria_principal_id` FK directa; NO agregar es_principal al puente. La entrega 1 documenta el corte y reporta candidatos; la entrega 2 de este cambio solo migra catalogo. La FK nullable de Producto se disena aqui, pero su implementacion se reserva a entrega 7 para no expandir alcance actual.

En entrega 7: agregar FK nullable, copiar solo relaciones inequivocas (incluidos buckets B3 validos), bloquear casos cero/multiples, pasar lectores/escritores a FK con adaptador legacy explicito y una sola autoridad de escritura, activar CHECK de producto activo con categoria, adaptar B3, y retirar puente solo tras demostrar ausencia de consumidores en entrega 8. No activar CHECK ni abandonar escrituras actuales en 1-6. No doble escritura no coordinada ni retirada temprana de columnas. El alcance actual no declara resuelta la atomicidad global de Producto.

Mientras el puente siga vigente, el resolver administrativo recibe una categoria unica; las comprobaciones de impacto usan relaciones legacy inequivocas o rechazan ambiguedad sin combinar ramas. Los cambios administrativos que no puedan demostrar completitud se bloquean. El escritor legacy de Producto sigue siendo una limitacion conocida hasta la entrega 7.

### 3. Integridad historica y preflight

Preflight reproducible de solo lectura, con IDs/rutas legibles y salida no cero ante bloqueos: nombres activos de atributo; codigos; asignaciones historicas duplicadas; hermanos duplicados activos/inactivos; ciclos; flags padre inconsistentes; cero/multiples categorias de producto; categoria invalida/B3; valores obligatorios faltantes; candidatos a anotacion de unidad. Solo candidatos declarados explicitamente: no inferir unidades por nombre.

Alembic revisiones nuevas, sin editar migraciones aplicadas. Constraints: codigo de atributo global normalizado unico; nombre de atributo activo normalizado unico; UNIQUE(categoria_id, atributo_id) historico; hermanos normalizados historicamente unicos con indices separados para raiz e hijos, sin filtro activo. Validacion servicio mas constraints y captura de IntegrityError -> mismo 409, incluidas carreras. Si hay duplicados historicos, detener upgrade; ninguna fusion, borrado, renombrado o seleccion arbitraria automatica.

Reactivate categoria ordinaria conserva ID, verifica padre/jerarquia/completitud y unicidad. No reactiva productos ni asignaciones por inferencia; estos conservan sus estados propios y requieren acciones explicitas. Para bucket B3 inactivo, el sistema reutiliza la misma fila y la reactiva internamente bajo lock; usuario no puede crear, editar, mover, elegir, reactivar o eliminar un bucket temporal.

### 4. Jerarquia y resolver

POST/PUT canonicos no reciben es_padre; read expone tiene_hijos calculado con hijos activos. Columna legacy permanece como proyeccion de compatibilidad reconciliada; no es autoridad. Prohibir auto-padre/ciclos/padre inactivo/default. Derivar hoja transaccionalmente, incluida carrera de crear hijo vs asignar producto. B3 solo con new_parent_id no nulo: lock padre, crear/reusar bucket, mover clasificacion legacy y auditar en misma transaccion. Mover a raiz no llama B3. Conteos globales no dependen de empresa seleccionada.

Un resolver backend reutiliza CTE/ranking por menor profundidad de categorias/relaciones/atributos activos. Una categoria por invocacion. Un mismo atributo_id tiene un solo mapping efectivo; override de hijo reemplaza obligatorio/default/orden completos, incluidos null deliberados (no COALESCE al padre). No excluir_heredado. Orden: CASE orden IS NULL, orden ASC, lower(trim(nombre)) ASC, atributo_id ASC. Hermanos: lower(trim(nombre)), id. Nunca depender del orden natural o del tratamiento implicito de NULL.

El resolver sirve panel, EAV, impactos y backfill, y posteriormente Producto/imports. No recorrer ancestros en FE como fallback funcional. Aplicar paginacion/limites de respuesta y conteos con consultas de conjunto, sin una consulta por nodo. Arbol sin profundidad fija; ciclos corruptos se detectan en preflight y se rechazan en lectura, no se recorren indefinidamente.

### 5. Asignaciones y completitud

Asignar existente: crear si no existe, 409 ATTRIBUTE_ALREADY_ASSIGNED si activa, reactivar mismo ID si inactiva tras validar configuracion. Crear definicion y asignar es una unica transaccion. codigo estable snake_case generado al alta; colisiones de codigo bloquean sin renombrar atributos arbitrariamente; renombrar etiqueta no cambia codigo.

Configuracion local modifica solo orden/obligatorio/default. Override crea/reactiva mapping hijo y no actualiza el mapping de origen. Campo omitido conserva; null limpia default/orden; valor reemplaza. Un default explicito se valida y canoniza con las mismas reglas EAV (incluye select/catalog, limites, negativos) independientemente de que sea opcional u obligatorio. Nunca N/A/0/false/fecha/primera opcion inferidos.

aplicar_default_a_existentes es boolean false por defecto en crear/asignar/update. Requerido sin default es valido si no introduce faltantes. Preview cuenta productos activos, valores validos faltantes, categorias afectadas y overrides. Si faltan obligatorios: 409 PRODUCT_REQUIRED_ATTRIBUTES_MISSING con conteos/IDs accionables; solo continuar con valores validos o default explicito+opt-in en misma transaccion. No remediacion persistente. Un remapeo pendiente no cuenta como valor valido: conversion que invalida obligatorios se bloquea sin escribir. Conversion de opcionales conserva original/remapeo conforme al ciclo existente.

Backfill fill-only, idempotente y consciente de overrides: solo productos a los que este mapping es efectivo, activos y sin valor activo definido; no modificar valores existentes ni convertirlos. Ante fila inactiva preservada, reutilizar la identidad con snapshot/auditoria de restauracion si corresponde; no insertar violando la unicidad ni sobrescribir historia sin trazabilidad. Un valor activo incompatible debe corregirse/remapearse explicitamente, no se sustituye como supuesto faltante.

Quitar mapping requiere preview del estado efectivo resultante, conserva otra asignacion aplicable si existe, valida la obligatoriedad resultante y solo inactiva EAV que deja de aplicar. Baja global usa snapshot existente e inactiva atributo/mappings/EAV activos; bloquea remapeos pendientes. Reactivacion y undo siguen compare-and-set; legacy sin snapshot falla de forma legible sin restauracion parcial.

### 6. Unidad y semantica historica

Modulo comun Unidad: UUID, codigo unico case-insensitive, nombre, simbolo exacto unico case-sensitive, magnitud_codigo extensible, es_sistema, activo y auditoria. No convertir MB/Mb ni GB/GiB. Codigo estable tras uso. Seed idempotente protegido completo de v2: UNIDAD/u/COUNT; GRAMO/g, KILOGRAMO/kg, LIBRA/lb/MASS; MILILITRO/mL, LITRO/L/VOLUME; MILIMETRO/mm, CENTIMETRO/cm, METRO/m, PULGADA/in/LENGTH; SEGUNDO/s, MINUTO/min, HORA/h/TIME; MEGABYTE/MB, GIGABYTE/GB, TERABYTE/TB, MEBIBYTE/MiB, GIBIBYTE/GiB/DATA_STORAGE; MEGAHERCIO/MHz, GIGAHERCIO/GHz/FREQUENCY; PUNTOS_POR_PULGADA/dpi/RESOLUTION_DENSITY; PORCENTAJE/%/PERCENTAGE. Nombres legibles del documento, sin acoplamiento al rubro.

Unidad de sistema no editable/desactivable por API; correcciones controladas por migracion posterior. Unidad usada por atributos activos/inactivos, defaults o snapshots no puede darse de baja ni cambiar codigo/simbolo/magnitud. Nombre descriptivo de unidad no sistema puede corregirse con auditoria sin cambiar significado. Reactivacion de unidad no sistema sin conflictos. Unidad_id nullable en Atributo, FK, solo integer/decimal; no boolean usa_unidad. Valores/defaults mantienen numero sin sufijo. El uso de magnitud clasifica unidades; no implica conversion ni inferencia semantica del atributo por nombre.

Sin EAV ni referencias historicas relevantes: agregar/cambiar/quitar unidad validando tipo y estado. Con datos: null -> unidad requiere preview y confirmar_anotacion_unidad=true; no altera numeros/defaults. A -> B bloquea ATTRIBUTE_UNIT_CHANGE_REQUIRES_CONVERSION; A -> null bloquea ATTRIBUTE_UNIT_REMOVAL_REQUIRES_MIGRATION. Undo de una anotacion es la excepcion controlada a esta ultima regla: restaura el snapshot anterior solo si post-estado exacto sigue intacto; no permite quitar unidad por PUT ordinario.

Snapshots incluyen codigo/unidad_id. Para snapshots legacy sin campos nuevos: interpretar version conocida con unidad ausente = null; conservar codigo estable generado sin reescribir historia; bloquear restauraciones ambiguas con 409, nunca degradar silenciosamente. Proteger unidades referenciadas en JSON mediante comprobacion transaccional; no hay FK desde JSON, por eso se requieren pruebas concurrentes de baja vs anotacion/undo.

### 7. Contrato coordinado

Base `/api/v1`; registrar rutas estaticas antes de `/{id}`. DTO/read OpenAPI es autoridad y se verifica en FE.

| Superficie | Contrato objetivo entregas 1-6 |
| --- | --- |
| Categorias | GET /categorias, /categorias/arbol, /categorias/seleccionables, /categorias/{id}; POST /categorias; PUT/DELETE /categorias/{id}; POST /categorias/{id}/reactivar |
| Atributos efectivos | GET /categorias/{id}/atributos-efectivos y /atributos-propios |
| Asignacion | POST /categorias/{id}/atributos y /atributos/previsualizar; PUT/DELETE /categorias/{id}/atributos/{mapping_id}; POST /categorias/{id}/atributos/{mapping_id}/previsualizar y /reactivar |
| Crear y asignar | POST /atributos con categoria_id y definicion/configuracion, commit unico; permitir atributo_id existente en contrato contextual sin recrear definicion |
| Ciclo atributo | GET /atributos y /{id}; PUT/DELETE /atributos/{id}; POST /{id}/previsualizar, /revertir, /reactivar; GET /{id}/reversion |
| Unidades | GET/POST /unidades; GET/PUT/DELETE /unidades/{id}; POST /unidades/{id}/reactivar; filtros q, magnitud_codigo, only_active, limit, offset |

Arbol: id, nombre, parent_id, tiene_hijos, is_default, atributos_propios_count, atributos_efectivos_count, hijos. Seleccionables: hojas activas no default; no modifica formulario Producto aun. Efectivos: mapping_id, atributo_id, codigo, nombre, tipo_dato, unidad{id,codigo,nombre,simbolo,magnitud_codigo}|null, restricciones, select_options, catalog_id, obligatorio, valor_default, orden, categoria_origen{id,nombre}, profundidad, heredado.

Preview read-only devuelve operacion, resumen, conteos, faltantes, conversiones/incompatibles/remapeos, cambio_unidad, requiere_confirmacion, acciones_permitidas, precondicion_preview. El token/precondicion es opaco y autenticado, con version, operacion, target, actor, payload normalizado, huella completa de estado relevante y expiracion; preview no crea filas. FE reenvia precondicion_preview en confirmacion junto con payload exacto y flags explicitos. Actualizar bajo locks y recalcular huella: 409 CATALOG_PREVIEW_STALE si cambio objetivo, estado, payload o expiracion; ningun commit parcial. No usar solo updated_at del atributo porque no cubre nuevas filas o cambios de herencia.

detail uniforme: code, message, conteos, affected_ids (cuando autorizado), acciones_permitidas. Codigos canonicos: CATEGORY_DUPLICATE_NAME, CATEGORY_CYCLE, CATEGORY_PARENT_INACTIVE, CATEGORY_NOT_LEAF, CATEGORY_DEFAULT_PROTECTED, CATEGORY_HAS_ACTIVE_CHILDREN, CATEGORY_PRODUCTS_HAVE_STOCK, CATEGORY_CHANGE_REQUIRES_CONFIRMATION; ATTRIBUTE_DUPLICATE_NAME, ATTRIBUTE_DUPLICATE_CODE, ATTRIBUTE_NOT_APPLICABLE, ATTRIBUTE_ALREADY_ASSIGNED, ATTRIBUTE_INVALID_TYPE, ATTRIBUTE_HAS_PENDING_REMAPS, ATTRIBUTE_STATE_CHANGED, ATTRIBUTE_UNIT_INVALID_TYPE, ATTRIBUTE_UNIT_ANNOTATION_REQUIRES_CONFIRMATION, ATTRIBUTE_UNIT_CHANGE_REQUIRES_CONVERSION, ATTRIBUTE_UNIT_REMOVAL_REQUIRES_MIGRATION; CATEGORY_ATTRIBUTE_IN_USE, CATEGORY_ATTRIBUTE_REMOVAL_REQUIRES_CONFIRMATION, REQUIRED_ATTRIBUTE_MISSING, DEFAULT_VALUE_INVALID, PRODUCT_REQUIRED_ATTRIBUTES_MISSING; UNIT_DUPLICATE_CODE, UNIT_DUPLICATE_SYMBOL, UNIT_IN_USE, UNIT_PROTECTED, UNIT_INACTIVE; CATALOG_PREVIEW_STALE. PRODUCT_CATEGORY_REQUIRED y PRODUCT_CATEGORY_NOT_LEAF se reservan a contrato de entrega 7; no usar codigos de cola de remediacion.

### 8. Seguridad, locks y atomicidad

Permisos efectivos CATEGORIAS/ATRIBUTOS/UNIDADES/PRODUCTOS con leer/crear/actualizar/eliminar; roles no son autorizacion suficiente. Configurar mapping requiere CATEGORIAS.actualizar + ATRIBUTOS.leer; edicion global ATRIBUTOS.actualizar; baja global ATRIBUTOS.eliminar. JWT/contexto autoritativo vence usuario_auditoria legado. Lecturas tambien autorizadas.

Servicio exterior es dueno de commit/rollback; helpers no hacen commit. Todas las mutaciones que afectan significado/completitud comparten locks deterministas de categorias, atributos, unidades, mappings y productos afectados, incluido INSERT de relaciones nuevas; locks de filas existentes solos no impiden fantasmas. Definir y probar orden consistente, guard comun de escrituras y constraints DB. En bridge ambiguo bloquear en vez de combinar ramas. Preview nunca escribe.

Auditar antes/despues, actor y operacion: CREATE/MOVE/DELETE/REACTIVATE_CATEGORY, CATEGORY_B3_RECLASSIFY; CREATE/UPDATE/DEACTIVATE/REACTIVATE_ATTRIBUTE, UNDO_ATTRIBUTE_CHANGE, ANNOTATE_ATTRIBUTE_UNIT; ASSIGN/OVERRIDE/UPDATE/REMOVE_CATEGORY_ATTRIBUTE, BACKFILL_CATEGORY_ATTRIBUTE; CREATE/UPDATE/DEACTIVATE/REACTIVATE_UNIT. Rollback de auditoria falla toda la operacion. No alterar cantidades, impuestos ni documentos historicos.

## Risks / Trade-offs

- Cambios de contrato/defaults -> publicar contrato nuevo, desplegar BE compatible y FE administrativo, retirar semantica legacy solo tras inventario de clientes; no mantener defaults artificiales como fallback oculto.
- Unicidad historica con datos existentes -> preflight bloqueante y conciliacion humana previa a constraints; no ejecutar upgrades en development/productivo durante planificacion.
- Herencia con datos concurrentes -> protocolo de locks en todos los caminos mutantes, huella de preview, pruebas PostgreSQL de nuevas filas/override y rollback.
- Snapshots JSON sin FK -> indice/consulta de referencias historicas y locks de unidad; no purga en esta fase.
- Producto legacy -> entregas 1-6 no anuncian producto atomico ni garantia completa del escritor antiguo; entrega 7 es gate separado obligatorio antes de cierre integral.

## Migration Plan

1. Entrega 1: contratos y preflight solo lectura, fixtures representativos y lista de consumidores. Resolver datos ambiguos por decisiones documentadas.
2. Entrega 2: nuevas revisiones Alembic de catalogo: codigo estable, Unidad/seed y unidad_id, unicidades historicas y proyeccion padre. No migrar Producto en este cambio. No SQLModel.metadata.create_all en runtime.
3. Entregas 3-6: desplegar primero BE compatible/autorizado, luego FE administrativo de mismo gate. Compatibilidad de escrituras debe ser explicita y temporal, nunca dos fuentes de verdad.
4. Verificar upgrade/downgrade/upgrade en schema PostgreSQL aislado y SQLite Core cuando proceda, con datos legacy. Downgrade bloquea si perderia unidad/codigo/historia o garantias activas; no borrar recuperacion para que un test pase.
5. Rollback operativo: deshabilitar acciones nuevas preservando schema y snapshots. No volver a defaults implicitos ni borrar seeds usados. Entregas 7-8 necesitan autorizacion y cambio posterior para FK/check/puente y E2E de Producto.

## Open Questions

No decisiones funcionales abiertas: aplicar v2 y los cuatro ajustes. La entrega 1 debe producir decisiones tecnicas verificables de huella/locks, compatibilidad de clientes y estado real del preflight. Una ambiguedad de datos bloquea el gate; no se resuelve ampliando alcance.