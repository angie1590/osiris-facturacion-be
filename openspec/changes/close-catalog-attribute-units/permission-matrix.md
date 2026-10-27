# BE1.7 - Base de permisos de catalogo

Alcance: base reutilizable, sin registro de rutas, seeds, credenciales, migraciones
ni cambios de handlers. Esta matriz no demuestra autorizacion en endpoints
desplegados ni completa el gate BE/FE. No modifica tareas OpenSpec.

## API

- `CATALOG_PERMISSIONS`: mapping inmutable de operacion a tupla de permisos.
- `CatalogOperation`: Literal de las operaciones admitidas.
- `require_catalog_permission(session, user_id, operation) -> Usuario`: comprueba
  usuario y rol activos y todos los permisos efectivos mediante `requiere_permiso`.
  No establece contexto de auditoria; el caller debe pasar una identidad ya
  autenticada, nunca un ID procedente del payload.
- `catalog_permission(operation) -> Callable[..., AsyncGenerator[Usuario, None]]`:
  dependencia para `actor: Usuario = Depends(catalog_permission(...))`.
  Usa `get_current_usuario` (access JWT), devuelve el usuario comprobado y establece
  `audit_context` durante el caller. Restaura el contexto anterior incluso si falla.
- Operacion desconocida: error de configuracion `KeyError`, nunca acceso permisivo.

Todos los requisitos de cada fila se combinan con AND, no OR. Las etiquetas de rol
no conceden acceso. Usuario, rol, modulo o concesion ausentes/inactivos deniegan.
La autenticacion conserva los 401 de `get_current_usuario`; permisos insuficientes
producen 403. Un permiso de escritura no implica lectura ni otro permiso de escritura.

## Matriz

| Operacion | Permisos efectivos requeridos | Evento previsto del caller |
| --- | --- | --- |
| `read_categories` (lista, detalle, arbol, seleccionables) | CATEGORIAS.leer | Sin mutacion |
| `create_category` | CATEGORIAS.crear | CREATE_CATEGORY; CATEGORY_B3_RECLASSIFY si corresponde |
| `update_category` | CATEGORIAS.actualizar | UPDATE_CATEGORY |
| `move_category` | CATEGORIAS.actualizar | MOVE_CATEGORY; CATEGORY_B3_RECLASSIFY si corresponde |
| `deactivate_category` | CATEGORIAS.eliminar | DELETE_CATEGORY |
| `reactivate_category` | CATEGORIAS.actualizar | REACTIVATE_CATEGORY |
| `read_category_attributes` (propios/efectivos) | CATEGORIAS.leer + ATRIBUTOS.leer | Sin mutacion |
| `configure_mapping` | CATEGORIAS.actualizar + ATRIBUTOS.leer | UPDATE_CATEGORY_ATTRIBUTE |
| `assign_attribute` | CATEGORIAS.actualizar + ATRIBUTOS.leer | ASSIGN_CATEGORY_ATTRIBUTE |
| `override_mapping` | CATEGORIAS.actualizar + ATRIBUTOS.leer | OVERRIDE_CATEGORY_ATTRIBUTE |
| `remove_mapping` | CATEGORIAS.actualizar + ATRIBUTOS.leer | REMOVE_CATEGORY_ATTRIBUTE |
| `reactivate_mapping` | CATEGORIAS.actualizar + ATRIBUTOS.leer | ASSIGN_CATEGORY_ATTRIBUTE, conservando identidad |
| `backfill_mapping` | CATEGORIAS.actualizar + ATRIBUTOS.leer | BACKFILL_CATEGORY_ATTRIBUTE |
| `preview_mapping` (configuracion/asignacion/quitar/backfill) | CATEGORIAS.actualizar + ATRIBUTOS.leer | Sin mutacion |
| `create_and_assign_attribute` | CATEGORIAS.actualizar + ATRIBUTOS.leer + ATRIBUTOS.crear | CREATE_ATTRIBUTE + ASSIGN_CATEGORY_ATTRIBUTE |
| `read_attributes` (incluye historial/reversion) | ATRIBUTOS.leer | Sin mutacion |
| `create_attribute` | ATRIBUTOS.crear | CREATE_ATTRIBUTE |
| `update_attribute` | ATRIBUTOS.actualizar | UPDATE_ATTRIBUTE |
| `deactivate_attribute` | ATRIBUTOS.eliminar | DEACTIVATE_ATTRIBUTE |
| `reactivate_attribute` | ATRIBUTOS.actualizar | REACTIVATE_ATTRIBUTE |
| `undo_attribute_change` | ATRIBUTOS.actualizar | UNDO_ATTRIBUTE_CHANGE |
| `annotate_attribute_unit` | ATRIBUTOS.actualizar | ANNOTATE_ATTRIBUTE_UNIT |
| `preview_attribute_update` | ATRIBUTOS.actualizar | Sin mutacion |
| `preview_attribute_deactivation` | ATRIBUTOS.eliminar | Sin mutacion |
| `read_units` | UNIDADES.leer | Sin mutacion |
| `create_unit` | UNIDADES.crear | CREATE_UNIT |
| `update_unit` | UNIDADES.actualizar | UPDATE_UNIT |
| `deactivate_unit` | UNIDADES.eliminar | DEACTIVATE_UNIT |
| `reactivate_unit` | UNIDADES.actualizar | REACTIVATE_UNIT |

Los eventos son contrato para consumidores futuros, no eventos emitidos por el
guard. Los previews deben escoger el permiso de la operacion final, no utilizar
lectura para autorizar impacto de escritura. Un preview de crear-y-asignar debe
usar `create_and_assign_attribute`, no `preview_mapping`.

## Actor y transaccion

La dependencia no recibe `usuario_auditoria`, rol ni identidad del frontend.
El actor consumido por el caller es el usuario autenticado; el contexto usado por
`record_domain_change` se establece con ese mismo ID. Payload y X-User-Id no
sustituyen esa autoridad. No se interpreta un JWT sin verificar en esta base.

El helper usa `no_autoflush`: autorizar/denegar no descarga trabajo pendiente,
no hace commit ni rollback y no registra auditoria de denegacion. No reutiliza el
rollback/commit de denegaciones del Directorio ni depende de ese modulo.
El servicio exterior conserva la propiedad de la transaccion y debe garantizar
atomicidad de dominio, snapshots y auditoria. No hay garantia nueva para handlers
legacy, concurrencia, locks, invariantes de unidades ni escrituras de Producto.

## Evidencia y limites

Las pruebas recorren todas las combinaciones de concesiones por operacion usando
el dispatcher FastAPI, una tabla de dominio aislada, RBAC SQLModel real y SQLite.
Verifican 403 sin ejecutar el caller ni emitir INSERT/UPDATE/DELETE, roles y
registros activos, ausencia de bypass admin y aislamiento de permisos por accion.

Un caller de prueba consume el actor y crea un evento real
`UPDATE_CATEGORY_ATTRIBUTE` mediante `record_domain_change`; tanto el registro de
dominio como el evento conservan el actor autenticado frente al payload falsificado.
Un rollback exterior elimina ambos. Se comprueba tambien trabajo exterior previo
y pendiente sin flush/commit/rollback del helper y restauracion del contexto.

No se generan tokens ni credenciales: las pruebas del dispatcher sustituyen solo
la frontera `decode_token`, manteniendo `get_current_usuario` real, y comprueban
rechazo de requests anonimos y tipos distintos de access. No constituyen prueba
criptografica de firmas JWT, prueba PostgreSQL ni prueba de endpoints existentes.