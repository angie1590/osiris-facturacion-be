# Conciliacion autorizada de datos de prueba

Fecha de revision: 2026-10-25. El mantenedor confirmo que son datos de prueba y autorizo su conciliacion, incluso su eliminacion si fuera necesaria. No se eliminaron filas: fue suficiente preservar identidades y referencias.

## Plan aplicado

- Comando: scripts/reconcile_test_catalog.py contra development local, host 127.0.0.1 puerto 5435.
- Previsualizacion por defecto: READ ONLY, sin cambios.
- Confirmacion explicita: --apply-test-data y --expected-plan-hash.
- Hash revisado/aplicado: d82566d9ff46e75a8e32f8c6e4d666939594e0dcf21723ea3d010f76495359bf.
- Actor de mantenimiento: maintenance:catalog-test-reconciliation.
- Resultado: 8 filas inactivas actualizadas, 4 renombres historicos y 5 flags padre corregidos (una fila tiene ambos cambios).
- Categorias activas, parent_id, estados activo, IDs y referencias no se modificaron. Los nombres inactivos duplicados recibieron un sufijo historico con su ID completo, sin elegir una fila para fusionar o borrar.

## Atomicidad y limites

El servicio requiere transaccion exterior y actor de auditoria; en PostgreSQL adquiere el guard advisory de catalogo y un lock de tabla que tambien bloquea escrituras legacy de categorias durante la aplicacion. Recalcula el plan y rechaza si su hash cambio. Cambios y eventos RECONCILE_TEST_CATEGORY se guardan en la misma transaccion. Si falla auditoria o postflight, se revierte todo.

La CLI rechaza aplicar sin hash o en entornos distintos de development/test/testing. Esta utilidad no es una migracion, no fusiona identidades y no corrige automaticamente otros conflictos, categorias temporales o duplicados activos. Tampoco cambia el escritor de Producto ni sus cantidades/impuestos.

## Evidencia

- Preflight antes: 7 conflictos (2 grupos historicos duplicados y 5 banderas inconsistentes).
- Preflight despues: apto_para_migrar=true, total_conflictos=0.
- Segunda previsualizacion: cambios pendientes=0.
- Auditoria verificada en lectura: 8 eventos del hash aplicado.
- Conteos conservados: 39 categorias, 21 atributos, 19 asignaciones, 19 productos, 19 clasificaciones y 106 valores; remapeos=0, snapshots de atributo=2 y valores de catalogo=7.
- tests/test_catalog_reconciliation.py: 7 passed (preservacion de filas/relaciones/valores, auditoria, idempotencia, plan obsoleto, rollback, actor requerido y CLI protegida).
- Suite backend completa: 945 passed, 11 skipped. Los skips no sustituyen pruebas de PostgreSQL de futuras migraciones.
- Ruff limpio; mypy del paquete (355 archivos) y de la CLI sin errores.
- No se ejecutaron migraciones ni se modifico codigo de Producto o frontend.

## Siguiente gate

El bloqueo de datos de entrada para la entrega 2 queda retirado. Aun faltan entidad/modelos Unidad, codigo/unidad_id, constraints y pruebas de migracion/compatibilidad; no declararlos desplegados porque el preflight este limpio. La advertencia ATTRIBUTE_CODE_NOT_DEPLOYED es esperada hasta su migracion aditiva.