# Entrega 3: jerarquía y B3

## Backend

- `CategoriaCreate`/`CategoriaUpdate` no publican `es_padre`; el adaptador de entrada ignora el flag legacy y `CategoriaService` lo deriva de hijos activos. El read expone `tiene_hijos` junto al alias legacy.
- `GET /api/v1/categorias/arbol` y `/seleccionables` usan permiso efectivo `CATEGORIAS.leer`, devuelven orden normalizado estable, conteos agrupados y bloquean ciclos/categorías huérfanas. Seleccionables excluye hojas temporales. Un CTE compartido calcula atributos efectivos para el resolver EAV multi-categoría y los conteos del árbol en lote, filtrando categorías/mappings/atributos inactivos y preservando mapping, origen, profundidad y overrides null. BE 3.5 completo.
- Create/update/delete/reactivate y writers de clasificación usan lock de catálogo PostgreSQL. Mover a `parent_id=null` no invoca B3; autociclos devuelven `CATEGORY_CYCLE`; padre inactivo y temporal usan errores canónicos.
- Crear/mover a un padre con productos directos requiere `confirmar_b3:true` y preview firmado. El token liga actor, operación, payload y estado (clasificaciones directas, padre, hijos y bucket); cambios responden `CATALOG_PREVIEW_STALE`. Sin consentimiento no se escribe.
- Endpoints: `POST /api/v1/categorias/previsualizar` para create y `POST /api/v1/categorias/{id}/previsualizar` para move. Confirmación reenvía payload tipado, `confirmar_b3: true` y token opaco. Snapshots OpenAPI objetivo FE/BE fueron regenerados desde la fuente común.
- La reactivación ordinaria conserva UUID, audita `REACTIVATE_CATEGORY` y no toca el estado independiente de productos/asignaciones. Nombre histórico equivalente sigue reservado.
- `Sin clasificar` rechaza create/rename/move/delete/reactivate manuales; ProductoService rechaza el destino con `CATEGORY_DEFAULT_PROTECTED`. B3 reutiliza el mismo ID histórico, lo reactiva, clasifica relaciones directas y audita; bucket vacío se desactiva con evento.
- API docs: `docs/docs/api/inventario/bloques-construccion.md` describe rutas, read alias, permisos y payload canónico.

## Evidencia

- `tests/test_categoria_tree.py`: árboles anidados, orden, conteos alineados con resolver EAV, precedencia local/default null/origen/mapping, filtros de inactivos, temporales no seleccionables, ciclo, guards HTTP, read alias, DTO write, raíz, reactivación y preview/confirmación/stale B3.
- El rol activo `admin`/`administrador` ahora tiene bypass central en guards por módulo y por rol; el endpoint de permisos refleja los grants y agrega los módulos de catálogo ausentes para que FE habilite la UI. Usuario/rol inactivos siguen bloqueados y roles normales conservan autorización explícita.
- E2E live API (usuario `Administrador`): create raíz + producto aislado sin stock, preview/confirmación B3 firmada, reclasificación al bucket, rechazo de DELETE manual del bucket, create hijo/nieto, selección de hoja, movimiento a raíz y reactivación conservando ID.
- Cleanup ejecutado con `DELETE` SQL por IDs/prefijo en `finally`: producto, relaciones producto-categoría, bucket/categorías y eventos de auditoría de la prueba. Verificación: **0** filas residuales de categorías/productos/vínculos/auditoría; totales globales de categorías/productos/vínculos quedaron exactamente en baseline (**39/19/19**).
- `tests/test_categoria_hierarchy_concurrency.py`: **2 passed** en PostgreSQL con schemas efímeros. Cubre crear hijo concurrente con clasificación de producto y dos hijos concurrentes que reutilizan un único B3 histórico.
- Ciclo de vida/stock: `test_categoria_baja.py`, `test_categoria_regla_b3.py`, `test_producto.py` y `test_producto_b3_regresion_e2e.py`.
- Revalidación backend: `poetry run rtk pytest -q`: **1229 passed, 75 skipped**; `ruff check .`, `mypy -p osiris` (367 archivos) y mypy focalizado correctos. Las pruebas PostgreSQL opt-in de concurrencia de jerarquía y locks: **9 passed**. OpenSpec estricto, auditoría API (**223 rutas, 0 faltantes**) y snapshot exportado correctos.
- Revalidación posterior al inicio de entrega 4: backend **1230 passed, 75 skipped**; Ruff, mypy (367 archivos), OpenSpec estricto, auditoría (**225 rutas, 0 faltantes**) y snapshot OpenAPI reproducible. Se verificaron también 9 pruebas PostgreSQL.
- Preflight desarrollo local: cero conflictos; se conservaron 39 categorías, 19 relaciones de categoría-producto, 19 asignaciones y 106 valores EAV.

## Límites del gate

El gate BE 3.7 se completó contra API real con una identidad aislada y cleanup SQL verificado; no quedaron datos ni auditorías de prueba. FE 3.5 se completó con tests, capturas responsive y recorrido por teclado. El formulario y el guardado de Producto permanecen sin cambios.

## Entrega 4: resolver efectivo (en curso)

- Completadas BE 4.1-4.3: CTE compartido para lecturas efectivas y conteos; DTO con mapping/origen/profundidad/unidad/restricciones/default; rutas autenticadas `atributos-efectivos` y `atributos-propios`; orden explícito primero y NULL-last determinista.
- Pruebas: override más cercano con `valor_default=null`, unidad expandida, propios vs heredados, orden explícito que contradice alfabético, inactive filtering y 401 anónimo. La validación EAV/Product legacy sigue consumiendo el mismo resolver.
- Pendientes BE 4.4-4.6: dirigir previews/backfill/completitud al resolver donde aplique, ampliar presupuesto de queries/ambigüedad legacy y cerrar gate con FE. No se inició entrega 5.