# Evidence: close-catalog-attribute-units

Fecha: 2026-10-27. Entorno: PostgreSQL local de desarrollo en `127.0.0.1:5435` para la prueba E2E, y schemas UUID aislados para pruebas PostgreSQL de integración. No se usaron datos productivos.

## Gates backend

| Gate | Evidencia |
|---|---|
| BE 5.10 / 6.7 | Recorrido administrativo FE contra API real: asignar existente, override, default null, backfill opt-in, quitar local, baja/reactivación global, alta/edición/protección de unidad, creación con/sin unidad, sufijo, anotación, conflicto A-B y undo. Los detalles están en el `evidence.md` del repositorio FE coordinado. |
| BE 7.1 | `poetry run rtk pytest -q`: 1268 passed, 76 skipped, 0 failed. Se aisló la suite del PostgreSQL local con DSN de conexión no disponible y se omitieron variables de pruebas live. |
| BE 7.2 | `poetry run ruff check .`: limpio. `MYPYPATH=src poetry run mypy -p osiris`: 370 archivos sin errores. |
| BE 7.3 | Migraciones, constraints y concurrencia PostgreSQL: 116 passed, 13 skipped. Se ejecutaron `test_catalog_integrity_migrations.py`, `test_attribute_code_concurrency.py`, `test_catalog_lock.py` y `test_categoria_hierarchy_concurrency.py`; las fixtures crean y eliminan schemas UUID. Los skips corresponden a una precondición SQLite y 12 casos de dos sesiones parametrizados que se omiten en SQLite; los casos PostgreSQL pasaron. |
| BE 7.4 | OpenAPI 3.1 expone 169 paths; presentes unidades, atributos propios/efectivos, preview de creación, preview de actualización y undo. No se llamó a operaciones de Producto, stock, cartera, SRI ni documentos. |
| BE 7.5 | API/checklist, flujo CU020 y guía de preflight/cleanup actualizados. La limpieza E2E quedó documentada por UUID y en orden FK. `npm run build` en `docs/` pasó tras escapar placeholders MDX literales. |

## Limpieza de la base local

La línea base antes de la UI E2E fue: categorías 39, atributos 21, mappings 19, snapshots 2, valores EAV 106, producto-categoría 19, unidades 22, remapeos 0 y `audit_log` 251. En una transacción se eliminaron únicamente los dos atributos `E2E_GATE_`, sus cuatro mappings, dos snapshots, 15 auditorías y la unidad temporal. No había valores EAV de esos atributos. Todos los conteos regresaron exactamente a la línea base y no quedó ninguna unidad/atributo con el prefijo de prueba.

El cambio anterior `manage-reversible-attribute-lifecycle` conserva sus checkboxes y estado propios; esta matriz no declara completadas sus tareas históricas.