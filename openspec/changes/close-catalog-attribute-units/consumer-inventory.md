# Inventario de consumidores - Entrega 1

Fecha: 2026-10-25. Alcance: inspeccion de consumidores actuales y preflight; no cambio de contratos runtime ni de autoridad de escritura.

## Contratos vigentes y dependencias

| Superficie | Consumidores comprobados | Transicion requerida |
| --- | --- | --- |
| Categoria.es_padre | entity.py/models.py/service.py de categoria; CategoriaCreate lo exige y CategoriaUpdate lo acepta | Publicar tiene_hijos calculado; retirar flag canonico solo despues del gate de clientes; columna legacy permanece |
| ProductoCategoria | producto/entity.py y repository.py reemplazan relaciones; producto/service.py carga y valida clasificacion y detalle | Puente es la fuente vigente; no crear FK directa ni segunda autoridad en entregas 1-6 |
| ProductoCategoria en B3 | categoria/service.py crea bucket, mueve relaciones, recategoriza y calcula pendientes/bajas | Mantener puente y proteger su escritura con protocolo comun antes de activar nuevas invariantes |
| ProductoCategoria en backfill | categoria_atributo/service.py usa CTE descendientes y puente para insertar defaults | Resolver mapping efectivo por producto y excluir overrides de hijos; no cambiar al formulario Producto |
| EAV aplicable | producto/service_atributos.py consulta puente y get_atributos_heredados_por_categorias | Consolidar resolver unico sin combinar ramas ambiguas |
| Resolver CTE | categoria/service.py y producto/service.py (detalle/esqueleto) | Filtros activos, mapping_id, origen, unidad y orden canonicos, conservando compatibilidad hasta entrega 7 |
| DTO de asignacion | categoria_atributo/models.py y router.py; campo de backfill optional y default no limpiable por null | Contrato omitido/null/valor y opt-in se cambia solo en entrega 5; no asumir ya desplegado |
| Definicion y snapshots | atributo/entity.py, models.py, service.py y router.py | Agregar codigo/unidad en entrega 2/6; preservar snapshots legacy e identidad |
| Actor y permisos | core/auth.py, permisos.py, audit_context.py; directory_permissions.py es precedente del guard efectivo | No extender el guard privado del Directorio como dependencia del catalogo; nueva matriz del catalogo debe verificar acciones y JWT |
| Scripts/seeds y pruebas | scripts/seed_complete_data.py, seed_sample_product.py y tests de categorias/productos son consumidores legacy | Revisar payloads es_padre/categoria_ids antes de retirar compatibilidad; no correr seeds en esta entrega |

## Acoplamiento frontend comprobado

- CategoriasPage envia es_padre=!parentId, calcula conteos/herencia con getAtributosAplicables, usa /categorias-atributos para listar/configurar y guarda definiciones con /atributos.
- features/categorias/api.ts y atributos-herencia.ts conservan DTO local del arbol; TreeSelector es solo representacion visual y no debe convertirse en autoridad de herencia.
- pages/catalog/RecategorizePage.tsx filtra por es_padre; requiere contrato de seleccionables antes de retirar bandera legacy.
- ProductosPage usa features/productos/api.ts: categoria_ids, getAtributosDeCategoria por relaciones directas y saveValoresProducto en segunda request. No modificar estos flujos en entrega 1.
- App mantiene redirects /atributos y /categorias-atributos. CategoriasAtributosPage.tsx sigue existiendo como pagina legacy; verificar referencias antes de retirarla, no asumir borrado seguro.

## Matriz de rollout

1. Publicar/adaptar DTO canonico y verificar fixtures de contrato BE/FE antes de habilitar acciones nuevas.
2. Adaptar lectores administrativos por gate, con rutas canonicas y cache por categoria; no fallback funcional local cuando falte endpoint.
3. Mantener la escritura actual de ProductoCategoria hasta entrega 7. Rechazar clasificaciones ambiguas en herramientas/operaciones nuevas en vez de elegir una rama.
4. La FK nullable, su CHECK y el corte de lectores/escritores Producto quedan en entrega 7. Retirada del puente solo en entrega 8 con inventario actualizado y pruebas.
5. Los contratos actuales de es_padre/defaults no se han cambiado al agregar este inventario. Las nuevas reglas no pueden anunciarse como disponibles todavia.

## Preflight implementado

CLI: scripts/audit_catalog_integrity.py; lector SQL Core: osiris.utils.catalog_preflight.audit_catalog.

- Incluye filas activas e inactivas; no depende de los filtros ORM ni importa routers para diagnosticar.
- Agrupa nombres de hermanos por parent_id y lower(trim(nombre)); codigo de atributo, si existe, se valida sin distinguir case. No genera codigos automaticamente.
- Detecta duplicados historicos de mapping, ciclos, padres invalidos y flag padre inconsistente.
- Audita producto activo con cero/multiples relaciones, categoria no hoja/inactiva/inexistente, bucket temporal estructuralmente invalido y valores obligatorios efectivos faltantes/incompatibles.
- Default configurado no cuenta como valor de producto. Cero/false son valores definidos; remapeo activo no satisface un obligatorio. Override opcional hijo prevalece sobre obligatorio ancestro.
- Candidatos de unidad requieren JSON explicito atributo_id -> unidad_codigo. Reporta valores activos/historicos y snapshots; no consulta una inferencia por nombre, no asigna unidad y no declara validado el destino del catalogo aun no desplegado.
- Reporte determinista con conflictos/IDs/nombres/rutas, conteos y warnings; --summary omite nombres/claves/IDs. Exit 0 = sin bloqueos de este diagnostico; 1 = conflictos o esquema incompleto; 2 = argumentos invalidos. Exit 0 no reemplaza gates de migracion/permisos/compatibilidad.
- CLI PostgreSQL usa REPEATABLE READ y SET TRANSACTION READ ONLY; no se ejecutan DDL/DML ni conciliaciones. Pruebas SQLite bloquean expresamente SQL mutante y comparan todas las filas antes/despues.

## Evidencia local de solo lectura

Comando ejecutado: `ENVIRONMENT=development PYTHONPATH=src poetry run python scripts/audit_catalog_integrity.py --host 127.0.0.1 --port 5435 --summary`.

Resultado: apto_para_migrar=false, 7 conflictos: 2 grupos CATEGORY_DUPLICATE_NAME y 5 CATEGORY_PARENT_FLAG_MISMATCH. Conteos: 39 categorias, 21 atributos, 19 mappings, 19 productos, 19 relaciones ProductoCategoria y 106 valores. La columna codigo aun no existe. Sin candidatos de anotacion indicados. No se corrigieron ni fusionaron filas. Este resultado bloquea el avance de migraciones dependientes hasta conciliacion explicita, no bloquea completar contratos/preflight de entrega 1.

## Estado del gate 1

Contratos objetivo publicados en contracts/catalog-administration-v1.openapi.json, con copia frontend identica y comprobacion reproducible por scripts/export_catalog_contract.py --check. Modelos y app contractual son aislados (501, NOT DEPLOYED), nunca montados en main. Schemas Zod, acceso efectivo y draft inmutable frontend verificados sin modificar pantallas.

catalog_permissions.py y permission-matrix.md definen 29 operaciones con AND de permisos, rol/usuario activos y actor JWT autoritativo; las pruebas usan dispatcher FastAPI y auditoria real en base aislada. catalog_lock.py aporta guard transaccional probado en PostgreSQL. Estos son fundamentos de entrega 1, no proteccion runtime de los endpoints legacy. Su conexion a todos los writers es gate obligatorio de cada entrega funcional, no se presume hecha ni se adelanta Producto.

Los 7 bloqueos de datos se conciliaron posteriormente con autorizacion explicita para datos de prueba; data-reconciliation.md contiene el plan aplicado y la evidencia de cero conflictos. Esto no equivale a implementar migraciones dependientes ni Producto atomico.

## Validacion del primer tramo

- `poetry run rtk pytest tests/test_catalog_preflight.py tests/test_catalog_preview.py -q`: 32 passed.
- `poetry run rtk pytest -q`: 746 passed, 8 skipped; no se cuentan los skips como evidencia de migracion/concurrencia PostgreSQL.
- `poetry run ruff check .`: limpio.
- `poetry run mypy -p osiris`: sin errores en 351 archivos.
- `MYPYPATH=src poetry run mypy --explicit-package-bases --follow-imports=silent scripts/audit_catalog_integrity.py`: limpio.
- Preflight PostgreSQL local READ ONLY ejecutado con salida resumen; 7 bloqueos registrados arriba, sin DML/DDL.
- Ninguna migracion aplicada ni formulario Producto modificado. Frontend tiene solo inventario y progreso documental en este tramo.

## Validacion coordinada del gate 1

- Suite backend completa: 938 passed, 11 skipped; los 3 skips del guard PostgreSQL se ejecutaron adicionalmente mediante configuracion local autorizada: tests/test_catalog_lock.py, 7 passed, solo SELECT y advisory locks, sin crear tablas ni alterar datos. Los otros 8 skips no se consideran evidencia de integracion.
- Ruff limpio; mypy -p osiris sin errores en 354 archivos; export_catalog_contract.py --check limpio.
- Suite frontend: 249 passed, lint y build correctos; cmp entre snapshots BE/FE sin diferencias.
- La revision cruzada corrigio AUTOCOMMIT efectivo a nivel engine, separacion global/local, rutas preview para todas las confirmaciones, error real del signer y UUID HTTP validos.
- Sin cambios a main, handlers existentes, pagina Producto o migraciones. Nuevos contratos/guards/helpers solo se consumen por pruebas hasta sus gates de integracion.

## Historico del bloqueo previo a entrega 2

- Raiz Tecnologia: una identidad activa y otra inactiva con el mismo nombre normalizado.
- Teclados bajo Tecnologia: tres identidades inactivas con el mismo nombre normalizado.
- Cinco flags padre inconsistentes: Muebles; Tecnologia (identidad historica); Tecnologia > Computadoras; Tecnologia > Perifericos; Tecnologia > Perifericos > Audifonos.
- Los IDs exactos salen del preflight completo. No se elige un superviviente ni se renombra/fusiona/borran identidades automaticamente. Las rutas pueden coincidir entre identidades historicas y requieren revisar IDs/referencias al preparar conciliacion.

Estado actual: conciliacion autorizada completada mediante plan con hash, 8 filas inactivas actualizadas y 8 eventos de auditoria; no hubo eliminaciones. Preflight limpio e idempotencia comprobada. El bloqueo de datos esta retirado; los gates de esquema/contratos de entrega 2 siguen pendientes.