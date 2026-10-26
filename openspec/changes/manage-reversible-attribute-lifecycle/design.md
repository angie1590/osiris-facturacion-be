## Context

`AtributoService.update` ya acepta definicion parcial y convierte valores tipados; las conversiones invalidas crean `ProductoAtributoRemapeo`. No se guarda la definicion ni el conjunto completo de valores pre-cambio. `delete` es soft delete generico y no limpia/reabre asignaciones `CategoriaAtributo` ni valores EAV. La pantalla `/atributos` lista/crea, aunque el API dispone de PUT y DELETE.

## Goals / Non-Goals

**Goals:** corregir nombre/definicion conservando ID, previsualizar impacto, validar restricciones nuevas tambien para el mismo tipo, preservar una version anterior completa y permitir rollback condicional, baja/reactivacion logica con asociaciones coherentes y UI comun sin formularios privados.

**Non-Goals:** borrar filas fisicamente, remapear valores a eleccion dentro de la transaccion inicial, editar valores EAV en productos, fusionar atributos/renombrar referencias globales, revertir escrituras posteriores arbitrarias, cambiar reglas tributarias, stock o documentos historicos.

## Decisions

1. **Snapshot append-only en PostgreSQL.** Nueva tabla `tbl_atributo_cambio` guarda actor/timestamps, atributo, operacion, definicion previa/posterior, asignaciones previas/posteriores, valores EAV previos/posteriores y estado de remapeos asociados. JSON permite conservar todos los campos tipados sin duplicar columnas de Producto. La migracion no modifica datos existentes; atributos inactivos anteriores a esta revision no obtienen historial artificial.
2. **Update completo por overlay parcial.** Mantener PUT compatible. Validar el merge de definicion existente/nueva. Un cambio de tipo, opciones SELECT/CATALOG o limites numericos revalida cada valor activo y crea remapeos para incompatibles; guardar snapshot y cambios dentro de una UoW/commit exterior. Nombre solamente guarda snapshot para poder deshacer correcciones.
3. **Preview sin escrituras.** `POST /atributos/{id}/previsualizar` acepta el mismo DTO de definicion parcial, resuelve solo catalogos existentes y devuelve cantidades de asignaciones/categorias, valores compatibles/remapeables y si requiere confirmacion. No crea/reactiva catalogos durante preview. UPDATE conserva los validadores y remapeos vigentes; preview no sustituye validacion final.
4. **Undo optimista y seguro.** `GET /atributos/{id}/reversion` devuelve la ultima operacion no revertida y motivo de bloqueo. `POST /atributos/{id}/revertir` comprueba dentro de transaccion que definicion, sets/IDs de asignaciones, valores activos/inactivos y remapeos asociados siguen exactamente como el snapshot posterior. Si un remapeo fue resuelto, aparecio/cambio un valor o se altero una asignacion, devuelve 409 y no escribe. En caso valido restaura snapshot anterior, inactiva remapeos creados por esa operacion y marca snapshot revertido, sin DELETE fisico.
5. **Baja logica transaccional reversible.** DELETE crea snapshot, rechaza con 409 si hay remapeos pendientes, inactiva Atributo, asignaciones de categoria y valores EAV en la misma unidad. Reactivacion explicita POST `/{id}/reactivar` revierte un snapshot de baja intacto; atributos legacy inactivos sin snapshot responden 409 con instruccion administrativa, no se reactivan parcialmente.
6. **Secuencia de historia.** Solo la ultima operacion puede revertirse. Revertir la mas reciente deja la anterior disponible si su estado posterior vuelve a coincidir. Cada update/reactivacion/reversion queda auditado por `record_domain_change`; snapshot conserva actor y timestamps.
7. **Frontend:** ampliar la tabla actual con Editar, Revertir, Dar de baja/Reactivar y filtro de activos/historial. Formulario de creacion/edicion reutiliza primitivas comunes. Un cambio que afecte valores abre preview y confirmacion; conflictos preservan formulario. No pagina paralela ni componentes privados nuevos.

## Risks / Trade-offs

- Snapshots JSON grandes -> JSON/JSONB aprovecha TOAST y filas solo de atributo cambiado; medir conteos en preview, no truncar silenciosamente. Si escala a millones de valores, evolucionar a tabla hija.
- Cambio concurrente durante revert -> bloquear atributo, asignaciones, valores y remapeos con `FOR UPDATE`, verificar snapshot despues del lock.
- Relacion SQLModel `valor_string` impone non-null? -> snapshots conservan exactamente valores tipados existentes; verificar constraint EAV y prueba PostgreSQL real.
- Resolver remapeo vuelve undo no seguro -> 409 explicito; opcion segura es crear una correccion inversa mediante nueva edicion, no forzar undo.
- Migracion/down revision -> downgrade bloquea si quedan snapshots no revertidos para no perder posibilidad de recuperacion.
- UI usa permisos actuales admin/supervisor. Errores/estados y detalle vienen del backend.

## Migration Plan

1. Crear revision Alembic append-only para snapshot con FK a Atributo e indices por atributo/fecha; preflight no destructivo.
2. Probar upgrade/downgrade en SQLite Core y PostgreSQL en schema aleatorio; downgrade se niega ante snapshots vigentes.
3. Desplegar endpoints y pruebas del servicio antes de habilitar editar/baja en UI.
4. Habilitar UI progresivamente; no reescribir snapshots de documentos, stock, auditoria previa ni historial EAV legacy.

Rollback: deshabilitar UI nueva y mantener CRUD actual; migration downgrade solamente cuando snapshots vigentes sean cero. No eliminar tabla con undo disponible ni revertir automaticamente filas productivas.

## Open Questions

No bloqueantes: definir retencion de snapshots historicos y eventual purga administrativa como capacidad posterior. En el MVP se retienen; no exponer PURGE.
