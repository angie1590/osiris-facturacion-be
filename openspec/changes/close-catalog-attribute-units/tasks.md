Ejecutar por entregas 1-6 coordinadas con el cambio frontend homonimo. Cada entrega depende de su predecesora y de su gate BE/FE; no marcar por mera existencia de codigo. La evidencia inicial de entrega 1 esta en consumer-inventory.md y preview-protocol.md; sus endpoints y gates integrados siguen pendientes.

## 1. Entrega 1 - Contratos y preflight

- [x] 1.1 Inventariar consumidores de es_padre, ProductoCategoria, resolver EAV y DTOs; fijar limites de compatibilidad sin tocar el formulario ni activar FK/CHECK de Producto.
- [x] 1.2 Publicar fixtures de contrato acordados con FE para arbol, seleccionables, efectivos/origen/unidad y operaciones contextuales; normalizar errores UNIT_DUPLICATE_CODE/SYMBOL y campos null/omitidos.
- [x] 1.3 Especificar y probar precondicion_preview autenticada: operacion/target/actor/payload/huella/version/expiracion; invalidar ante nueva fila, override, expiracion o payload distinto sin escribir en preview.
- [x] 1.4 Crear preflight de solo lectura con reporte/exit code para hermanos historicos duplicados, atributos/codigos/asignaciones duplicados, ciclos y flags padre inconsistentes; probar que no muta datos.
- [x] 1.5 Extender reporte para productos sin/multiples/invalidas categorias, buckets B3, faltantes obligatorios y candidatos explicitos a anotacion; incluir IDs accionables sin inferir unidades ni resolver ambiguedad automaticamente.
- [x] 1.6 Definir protocolo comun de locks y transacciones exteriores para jerarquia, atributos, mappings, unidades y productos; incluir inserciones fantasma y orden de adquisicion determinista.
- [x] 1.7 Mapear permisos efectivos de lectura/escritura y eventos de auditoria con actor JWT; demostrar 403 sin escrituras y rechazo del actor falsificado.
- [x] 1.8 Cerrar gate 1 con FE: pruebas de contratos/preflight/autorizacion, datos ambiguos reportados y matriz de consumidores/compatibilidad; no ejecutar conciliaciones ni migraciones destructivas.
- [x] 1.9 Conciliar datos locales de prueba tras autorizacion explicita: plan revisado, renombres historicos/flags, auditoria atomica, preservacion de referencias y postflight limpio; sin eliminar filas ni ejecutar migraciones.

## 2. Entrega 2 - Integridad aditiva de catalogo

- [x] 2.1 Implementar entidad/DTOs base Unidad y codigo estable de Atributo con tests; unidad_id nullable solo para tipos numericos, sin modelo de unidad comercial ni cambio de Producto.
- [x] 2.2 Crear nueva revision Alembic para codigo/unidad_id y tbl_unidad con FK, auditoria, simbolo exacto unico y codigo case-insensitive unico; sembrar las 22 unidades protegidas de v2 con identidades estables.
- [x] 2.3 Crear revision de unicidad historica de CategoriaAtributo y hermanos raiz/hijos normalizados; preflight bloqueante ante duplicados, sin fusion ni borrado automatico.
- [x] 2.4 Reconciliar columna es_padre como proyeccion legacy de hijos activos sin eliminarla; conservar IDs/relaciones y demostrar datos antes/despues.
- [x] 2.5 Implementar generacion estable snake_case de codigo y conflictos ATTRIBUTE_DUPLICATE_CODE; renombrar etiqueta no modifica codigo y colisiones no eligen semantica arbitraria.
- [x] 2.6 Probar constraints con SQL directo y dos sesiones PostgreSQL: hermanos/codigos/simbolos/mappings; convertir IntegrityError a 409 uniforme.
- [x] 2.7 Ensayar upgrade/downgrade/upgrade en schema PostgreSQL aislado con fixtures legacy; bloquear downgrade con historia referenciada, sin modificar migraciones ya aplicadas ni datos productivos.
- [x] 2.8 Cerrar gate 2 con FE: integridad documentada, compatibilidad de contratos/fixtures y evidencia de migracion; ninguna FK/CHECK/corte de Producto activada.

## 3. Entrega 3 - Categorias y B3

- [x] 3.1 Publicar tiene_hijos derivado y DTOs canonicos sin es_padre de escritura; mantener adaptador legacy explicito hasta verificar clientes, sin recuperar autoridad de bandera enviada.
- [x] 3.2 Corregir movimiento a raiz y probar ausencia de B3 con None, self/ciclos/padre inactivo/default, movimientos multinivel y conflictos de nombre sin efectos parciales.
- [x] 3.3 Implementar reactivacion autorizada de categoria ordinaria conservando ID sin restaurar productos/mappings implicitamente; rechazar recreacion equivalente de categoria inactiva.
- [x] 3.4 Proteger Sin clasificar en todas las mutaciones/selecciones manuales; reutilizar internamente bucket inactivo y desactivarlo al vaciarse, con transaccion B3 y auditoria.
- [x] 3.5 Exponer GET /categorias/arbol y /seleccionables con orden estable, control de ciclos y hojas activas no temporales; agregar conteos propios/efectivos mediante resolver compartido, no N+1.
- [x] 3.6 Probar concurrencia crear hijo vs clasificar, reactivar bucket vs crear hermano, baja con hijos/stock y cascada confirmada sin cambios de cantidades/documentos.
- [x] 3.7 Cerrar gate 3 con FE: recorridos raiz/hijo/nieto, seleccion padre, movimiento a raiz, temporal protegido y categoria ordinaria reactivada contra API real compatible.

## 4. Entrega 4 - Resolver efectivo canonico

- [x] 4.1 Consolidar resolver por categoria unica con CTE, filtros activos y prioridad por menor profundidad; conservar mapping_id/origen y override completo incluidos default/orden null.
- [x] 4.2 Implementar orden explicito NULL-last portable, nombre normalizado e ID; probar precedencia local, misma unidad canonica y desempates deterministas.
- [x] 4.3 Publicar GET /categorias/{id}/atributos-efectivos y /atributos-propios con definicion/unidad/restricciones/configuracion/origen; verificar OpenAPI con fixtures FE.
- [x] 4.4 Encaminar validacion EAV existente, conteos, previews y backfill al resolver comun; reportar clasificacion legacy ambigua sin combinar ramas ni cambiar el formulario Producto.
- [x] 4.5 Probar ancestros/mappings/atributos inactivos, override con null, ramas profundas, permisos y consultas de conjunto con presupuesto de queries.
- [x] 4.6 Cerrar gate 4 con FE: panel consume API efectiva y conteos de arbol, sin autoridad de herencia local ni regresion de EAV legacy.

## 5. Entrega 5 - Asignaciones, defaults y ciclo de vida

- [x] 5.1 Implementar asignar existente/create-and-assign atomico, conflicto activo y reactivar mapping historico con mismo ID; validar permisos y auditoria diferenciados.
- [x] 5.2 Implementar override local con mismo atributo_id sin alterar definicion global ni mapping ancestro; rechazar configuracion global en DTO de relacion.
- [x] 5.3 Eliminar defaults artificiales; soportar omitido/null/valor para default/orden, validar default incluso opcional contra caster/select/catalog/limites y canonizar sin simbolo.
- [x] 5.4 Hacer aplicar_default_a_existentes=false por defecto en todos los caminos, incluido create; probar que flag omitido no escribe EAV y requerido sin default es valido cuando no genera faltantes.
- [x] 5.5 Implementar preview de obligatorios con conteos/IDs y gate final de completitud bajo locks; bloquear conversion requerida incompatible aunque genere remapeo, y conservar remapeo reversible para opcionales.
- [x] 5.6 Implementar backfill explicito idempotente fill-only consciente de overrides y filas inactivas historicas; preservar valores activos y registrar recuperacion de identidad sin sobrescritura silenciosa.
- [x] 5.7 Implementar preview/quitar asignacion contextual, conservando EAV aun aplicable y desactivando solo no aplicable; validar obligatoriedad resultante y confirmar cuando existan valores afectados.
- [x] 5.8 Conectar baja global/reactivacion/undo existentes al protocolo compartido de precondicion/locks; probar legacy sin snapshot, remapeo resuelto, nuevas filas y rollback de auditoria/commit.
- [x] 5.9 Publicar rutas contextuales y errores definitivos; verificar actor JWT y ausencia de efectos en stock, impuestos y documentos historicos.
- [ ] 5.10 Cerrar gate 5 con FE: asignar/reusar/override/default-null/backfill/quitar-local/baja-global/restauracion, sin productos activos nuevos incompletos por estas operaciones administrativas.

## 6. Entrega 6 - Unidades de atributo

- [x] 6.1 Implementar CRUD/filtros/reactivacion Unidad con permisos efectivos; proteger seed y unicidad case-sensitive de simbolo/case-insensitive de codigo.
- [x] 6.2 Implementar calculo de uso actual/historico incluido JSON de snapshots; bloquear baja/codigo/simbolo/magnitud en uso, permitir solo correccion descriptiva auditada de no sistema.
- [ ] 6.3 Incluir unidad en create/read/update/efectivos/preview de atributo y defaults separados; rechazar unidad inactiva/no numerica sin convertir numeros.
- [ ] 6.4 Implementar anotacion inicial confirmada con precondicion_preview y confirmar_anotacion_unidad; contar datos activos/historicos y demostrar invariancia numerica/defaults.
- [ ] 6.5 Bloquear cambio A-B y retiro ordinario A-null con valores/historia; probar solo referencia historica y carrera baja unidad vs anotacion.
- [ ] 6.6 Extender snapshots/restore con codigo y unidad_id, politica legacy sin reescribir historia y undo de anotacion como excepcion condicional; bloquear ante post-estado cambiado.
- [ ] 6.7 Cerrar gate 6 con FE: administrar unidades, crear atributo con/sin unidad, default con sufijo, anotacion/409/undo en API real; sin unidad comercial ni formulario Producto.

## 7. Gates ejecutables de cierre del alcance actual

- [ ] 7.1 Ejecutar suite backend completa: `poetry run rtk pytest -q` (o `poetry run pytest` si el wrapper impide diagnostico); cero fallos, skips de integracion no cuentan como evidencia PostgreSQL.
- [ ] 7.2 Ejecutar `poetry run ruff check .` y `poetry run mypy -p osiris`, mas mypy de la superficie de scripts nueva cuando corresponda.
- [ ] 7.3 Ejecutar pruebas PostgreSQL aisladas de migracion y concurrencia, incluyendo upgrade/downgrade permitido y bloqueado; registrar fixtures/datos preservados sin usar bases reales para pruebas destructivas.
- [ ] 7.4 Verificar contratos OpenAPI compartidos y evidencia E2E administrativa con FE por entregas 1-6; auditar que no cambio stock/cartera/SRI/documentos ni codigo/formulario Producto fuera de adaptadores de impacto ya acordados.
- [ ] 7.5 Actualizar API/procesos/runbook/preflight y matriz de evidencia vinculada con manage-reversible-attribute-lifecycle; no cerrar ni archivar tareas antiguas sin evidencia especifica.
- [ ] 7.6 Ejecutar `openspec validate close-catalog-attribute-units --strict --no-interactive` en ambos repos y verificar alcance final antes de declarar completadas entregas 1-6.

## Fuera de esta ejecucion - Entregas futuras 7 y 8

No son tareas autorizadas por este cambio: implementar FK directa y cutover de Producto, activar CHECK de activos, modificar su formulario/alta atomica, retirar puente legacy o ejecutar cierre E2E integral de Producto. Requieren nueva autorizacion/cambio posterior despues de gates 1-6 verdes. No confundir la seccion 7 de gates anterior con la entrega funcional 7 del documento v2.