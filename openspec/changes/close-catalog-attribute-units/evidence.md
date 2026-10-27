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

## Seguimiento de auditoría H-01/H-02/H-03 (2026-10-27)

- H-01: GET legacy deprecado y protegido por `ATRIBUTOS.leer`; POST/PUT/DELETE responden 410 `LEGACY_CATEGORY_ATTRIBUTE_WRITE_DISABLED` antes de abrir sesión o tocar datos. OpenAPI marca las cinco operaciones deprecated y documenta 410. `ProductosPage` conserva el GET como consumidor transitorio; el componente FE de asignación sin ruta fue retirado. El smoke live confirma 410 sin escrituras y 401 anónimo en la ruta contextual.
- H-02: remapeos usan `ATRIBUTOS.leer/actualizar`; lectura B3 usa `CATEGORIAS.leer` y recategorización `CATEGORIAS.actualizar`. Pruebas API comprueban 403/200 con usuarios no-admin y grants efectivos. El actor de las rutas contextuales sigue derivado del JWT.
- H-03: E2E Playwright contra el API local/PostgreSQL creó dos productos activos temporales en una categoría hoja. A tenía EAV decimal 8; B no tenía valor. El preview obligatorio/backfill identificó el faltante y bloqueó sin opt-in; el backfill confirmado asignó 16 solo a B y preservó 8 en A. La anotación GB informó dos valores activos/ninguna conversión; el cambio GB-MiB devolvió 409, el undo restauró `unidad_id=null` y ambos valores; la conversión string-integer obligatoria con `n/a` devolvió `PRODUCT_REQUIRED_ATTRIBUTES_MISSING`; una modificación concurrente del mapping invalidó el preview con `CATALOG_PREVIEW_STALE`; retirar el override local conservó los dos EAV por herencia.
- Limpieza H-03: eliminados los dos productos, relaciones de categoría, dos atributos, tres mappings, cuatro valores EAV, un snapshot, usuario/persona temporal y auditoría asociada. Conteos restaurados a la línea base; no quedaron filas `E2E_H03_`. Productos tenían cantidad 0; no se modificaron impuestos, stock, ventas, compras, SRI ni documentos.
- Verificación final: suite BE completa, 1282 passed y 77 skipped; Ruff y mypy limpios (370 archivos); suite FE, 321 passed, lint y build limpios; Docusaurus build y `openspec validate --strict --no-interactive` en ambos repos pasaron. Live smoke contra el backend actualizado en `8003`: 2 passed (410 en POST/PUT/DELETE legacy y 401 anónimo en la escritura contextual). La instancia aislada se detuvo después de la prueba.