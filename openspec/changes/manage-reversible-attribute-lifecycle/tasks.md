## 1. Contrato y snapshot

- [x] 1.1 Verificar constraints/modelos actuales de Atributo, CategoriaAtributo, ProductoAtributoValor y ProductoAtributoRemapeo; fijar contratos OpenAPI preview/reversion/revertir/reactivar.
- [x] 1.2 Agregar entidad append-only AtributoCambio con definición, asignaciones, valores tipados y remapeos antes/después, actor y estado de reversión.
- [x] 1.3 Crear migración Alembic para historial/indexes/FK y downgrade bloqueante mientras existan snapshots sin revertir; probar fixtures legacy sin alterar filas existentes.
- [x] 1.4 Agregar helpers serializar/restaurar estado con Decimal/date/UUID/enum y snapshot de todas las filas relevantes incluyendo inactivas.

## 2. Preview y edición reversible

- [x] 2.1 Implementar previsualización de lectura para definición parcial, conversión, restricciones SELECT/CATALOG/numeric, conteos de valores y asignaciones; prohibir escrituras en preview.
- [x] 2.2 Refactorizar update para detectar cambios reales de definición/constricciones, guardar snapshot previo, convertir valores compatibles y crear remapeos sin perder originales.
- [x] 2.3 Persistir post-snapshot y auditoría en la misma transacción exterior; cubrir flush/commit fallido con rollback de valor, atributo, remapeo y snapshot.
- [x] 2.4 Implementar consulta de estado de reversión sobre la última operación no revertida con resumen y motivo cuando ya no sea segura.
- [x] 2.5 Implementar undo con locks/compare-and-set de definición y conjuntos exactos de filas valores/asignaciones/remapeos; conflicto 409 sin escrituras si difiere.
- [x] 2.6 Verificar que undo de tipo con remapeos pendientes restaura valores y desactiva remapeos; bloquear si un remapeo fue resuelto o cambió EAV.
- [x] 2.7 Probar secuencia edición A -> edición B -> undo B -> undo A; impedir revertir operación no más reciente.

## 3. Baja lógica y reactivación

- [x] 3.1 Antes de baja, consultar remapeos pendientes y bloquear con 409 detallado si existen.
- [x] 3.2 Snapshot y desactivar Atributo, asignaciones de categoría y valores EAV activos en una transacción, conservando todas las filas e IDs.
- [x] 3.3 Implementar reactivación explícita usando snapshot de baja; validar que el post-estado sigue intacto y restaurar estados previos de atributo/asignaciones/valores.
- [x] 3.4 Rechazar reactivación parcial de atributos legacy inactivos sin snapshot y verificar que baja/restauración no modifica snapshots de compras/ventas ni stock.
- [x] 3.5 Agregar endpoints POST preview, GET reversion, POST revertir y POST reactivar protegidos por rol admin/supervisor; preservar GET/POST/PUT/DELETE existentes.
- [x] 3.6 Permitir optar por backfill al cambiar asignación opcional a obligatoria; completar solo valores EAV faltantes y conservar los existentes.

## 4. Pruebas backend

- [x] 4.1 Probar PUT de nombre/campos por cada tipo y duplicados; misma identidad y asociaciones.
- [x] 4.2 Probar preview sin escrituras, conversiones y remapeos, SELECT options, catálogo inactivo y límites numéricos.
- [x] 4.3 Probar undo exacto exitoso, post-estado alterado, nueva fila EAV/asignación, remapeo resuelto, operación no reciente y rollback.
- [x] 4.4 Probar baja con/sin remapeos, restauración de hijos, ID histórico, legacy sin snapshot, y rollback ante fallo intermedio.
- [x] 4.5 Probar migración SQLite Core y PostgreSQL en schema aleatorio: upgrade, downgrade permitido/bloqueado y conservación de filas/FKs.
- [x] 4.6 Ejecutar tests atributo/configuración/remapeo/producto EAV; Ruff y mypy focalizado de la superficie.

## 5. API y documentación backend

- [x] 5.1 Documentar preview, estados de snapshot, conflictos 409, retención y reactivación en API de Atributos y remapeos.
- [x] 5.2 Ejecutar `openspec validate manage-reversible-attribute-lifecycle --strict --no-interactive` y revisar migración/contratos.
