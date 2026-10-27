# Entrega 4: resolver efectivo canónico

## Backend

- Un CTE recursivo compartido resuelve una categoría o un conjunto de categorías en lote, filtrando ancestros, mappings y atributos inactivos y evitando ciclos en la ruta. El mapping más cercano gana; conserva `mapping_id`, configuración completa (incluidos default/orden `null`), origen y profundidad.
- La respuesta canónica incluye `codigo`, nombre/tipo, unidad expandida, restricciones, opciones/catálogo, obligatoriedad, default, orden, `categoria_origen` y `heredado`. `GET /categorias/{id}/atributos-efectivos` devuelve el schema aplicable y `GET /categorias/{id}/atributos-propios` solo mappings directos; ambas rutas exigen lectura efectiva de Categorías+Atributos.
- Los conteos efectivos del árbol usan el mismo ranking por categoría. Orden determinista: orden no nulo primero y ascendente; luego nombre normalizado e ID. Los `null` quedan al final.
- La fachada EAV/Product legacy delega al mismo resolver. Una selección legacy con categorías en una sola cadena se normaliza al descendiente; ramas hermanas se rechazan con `409 CATEGORY_ATTRIBUTE_SCOPE_AMBIGUOUS`, sin combinar schemas. El GET completo de Producto propaga ese conflicto.
- El backfill usa resolución efectiva batch, solo afecta productos activos donde el mapping es efectivo, omite mappings sustituidos por overrides descendientes y bloquea clasificaciones múltiples ambiguas antes del `INSERT ... SELECT`. `AtributoService.preview_update` informa las categorías efectivas con `mapping_id` y origen usando el mismo resolver.

## Evidencia

- `tests/test_categoria_tree.py`: unidad expandida, mapping/origen, override null, propio/heredado, orden explícito no alfabético, inactive mapping/ancestor, permisos, ramas profundas y presupuesto de tres consultas del árbol.
- `tests/test_categoria_atributo.py`: backfill fill-only/idempotente, no sobrescribe valores activos, ignora el producto inactivo, respeta override hijo y rechaza ramas ambiguas sin insertar EAV.
- `tests/test_categoria_herencia_cte.py`: precedencia por cercanía, cadena ancestro-descendiente permitida y categorías hermanas rechazadas.
- `tests/test_atributo_conversion_remap.py`: preview global reporta mappings/origen efectivos incluyendo override local.
- Revalidación completa: **1236 passed, 75 skipped**; 9 pruebas PostgreSQL de concurrencia/locks; Ruff, mypy (367 archivos), mypy focal (9 archivos), OpenSpec estricto y auditoría API (**225 rutas, 0 faltantes**) correctos. Snapshot OpenAPI exportado idéntico al de FE.
- Smoke live de solo lectura con rol Administrador: Mouse devolvió **5 efectivos/3 propios**; Marca y Modelo se identificaron como heredados de Tecnología con default `null`. No se modificaron datos.

## Alcance

Entregas BE 4.1–4.6 completadas. El formulario y guardado de Producto no cambiaron. Las operaciones administrativas de asignación/default/backfill continúan en la entrega 5; no se inició esa entrega.
