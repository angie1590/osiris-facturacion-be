# Entrega 2: evidencia de integridad aditiva

## Implementacion y datos locales

- Revisiones nuevas: `e1a6c2d9b740` (unidad y codigo estable), `e2b7d3f0c851` (identidad historica y proyeccion `es_padre`) y `f04b7c2a9e61` (nulabilidad real de auditoria opcional). La revision previa `9d4b6f2a1c33` se corrigio para descubrir tablas de `current_schema()` y no consultar `public` al operar sobre schemas aislados.
- Preflight en PostgreSQL local `127.0.0.1:5435`, antes del upgrade: `apto_para_migrar=true`, cero conflictos. La columna `codigo` aun no existia; el reporte validaba codigos previstos y mostro esa advertencia esperada.
- La conciliacion previa renombro solo tres etiquetas inactivas (`Marca` una vez y `DPI` dos veces), preservando UUID, estado y relaciones. El hash revisado fue `b4953361fa55df981eac360eed1e2b365007fab4f6286ef31e724ee9d9c07c8d`. La auditoria contiene tres eventos `RECONCILE_TEST_ATTRIBUTE` con actor `maintenance:catalog-test-reconciliation`; no se anotaron unidades ni se convirtieron valores.
- Upgrade local aplicado hasta `f04b7c2a9e61`. Postflight readonly: 21 atributos con 21 codigos unicos, 22 unidades seed, cero conflictos; los conteos previos se conservaron: 39 categorias, 21 atributos, 19 asignaciones, 19 productos, 19 clasificaciones, 106 valores EAV, 0 remapeos, 2 snapshots y 7 valores de catalogo. DTOs `AtributoRead` validados: 21/21. La columna `unidad_id` quedo null para todos los atributos existentes.
- La revision de nulabilidad cambia `usuario_auditoria` a nullable solo en atributo/categoria/mapping, en concordancia con DTOs opcionales y escrituras sin actor. Downgrade restaura `NOT NULL` unicamente si no hay nulos. La prueba tambien verifica que los indices de expresion sobreviven la reconstruccion SQLite.
- La cadena completa desde `f277a59033e3` hasta `f04b7c2a9e61` se ejecuto en un schema PostgreSQL temporal: head correcto, 22 unidades y cero atributos con `usuario_auditoria` nulo. El schema se elimino al terminar.
- `compare_metadata` con tipos y defaults habilitados, limitado a `tbl_atributo`, `tbl_categoria`, `tbl_categoria_atributo` y `tbl_unidad`, reporta cero diferencias tras el upgrade local.
- API OpenAPI local respondio HTTP 200; la pantalla FE `/categorias` respondio HTTP 200. Esto no significa que el contrato objetivo aislado o CRUD de unidades este montado.

## Pruebas

- Suite BE: `poetry run rtk pytest -q`: 1204 passed, 73 skipped; `poetry run ruff check .` y `poetry run mypy -p osiris`: correctos (362 archivos).
- Migraciones e integridad/concurrencia en PostgreSQL aislado: 105 passed, 13 skipped por variantes SQLite. Las pruebas PostgreSQL de unicidad concurrente se ejecutaron; no se modifico `public` durante esta prueba.
- Migraciones sobre clon de la base actual: `c5e91a7d2b64 -> e1a6c2d9b740 -> e2b7d3f0c851 -> f04b7c2a9e61 -> c5e91a7d2b64 -> e2b7d3f0c851 -> f04b7c2a9e61`, correcto, incluidas 22 semillas. Downgrade productivo/local poblado no se intento; las guardas lo bloquean deliberadamente.
- Pruebas BE finales: `poetry run rtk pytest -q`: 1205 passed, 73 skipped; pruebas PostgreSQL aisladas de migracion/concurrencia: 106 passed, 13 skips especificos de SQLite.
- CLI/mypy de scripts y `scripts/export_catalog_contract.py --check`: correctos. Snapshot OpenAPI FE y BE identicos.
- FE: 278 pruebas en 27 archivos; lint y build correctos. Los tests de compatibilidad verifican 409 visibles y borrador intacto, ademas de lecturas aditivas/refetch en Categorias.
- `openspec validate close-catalog-attribute-units --strict --no-interactive`: ejecutar al cerrar esta entrega en ambos repositorios.

- No quedan diferencias de metadata en las cuatro tablas de catalogo auditadas ni bloqueo de fresh install. La inspeccion no cubrio todas las tablas ajenas a esta entrega; mantener revision manual de autogeneraciones fuera de este alcance.
- El contrato objetivo sigue aislado/no montado. No hay CRUD ni UI de Unidad, endpoints de arbol/atributos efectivos, ni cambios al formulario/guardado de Producto. Las entregas 3-6 y gates globales 7.1-7.6 permanecen pendientes.