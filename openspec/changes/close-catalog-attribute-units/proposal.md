## Why

El catalogo ya dispone de jerarquia, herencia, EAV tipado y snapshots, pero conserva contratos inconsistentes, defaults artificiales y duplicidad de reglas entre backend y frontend. El documento de arquitectura v2.0 del 25 de octubre de 2026 y sus cuatro ajustes operativos definen un cierre incremental sin reinterpretar datos ni anticipar la integracion atomica de Producto.

## What Changes

- Formalizar las entregas 1 a 6: preflight de solo lectura, integridad, categorias, atributos efectivos, asignaciones/defaults y unidades de atributo, con permisos efectivos y auditoria en cada entrega.
- Derivar `tiene_hijos`, proteger `Sin clasificar`, corregir movimiento a raiz y respaldar nombres de hermanos normalizados con unicidad historica en DB. Agregar reactivacion explicita de categorias ordinarias y reutilizacion interna de buckets B3.
- Consolidar un resolver backend por categoria, con origen, override mas especifico y orden explicito antes de nombre/ID. Publicar arbol, seleccionables y atributos efectivos.
- Habilitar reutilizacion de atributos canonicos con codigo estable, identidad historica de asignacion y distincion entre quitar localmente y baja global.
- **BREAKING**: eliminar defaults inventados; flag omitido de backfill equivale a false; distinguir campo omitido de null. Rechazar cambios que introduzcan faltantes obligatorios, incluidas conversiones incompatibles de atributos obligatorios.
- Agregar `Unidad`, seed protegido, unidad opcional numerica, anotacion inicial confirmada y proteccion por uso actual/historico. Integrar codigo/unidad con preview, snapshot y undo condicional de anotacion.
- **BREAKING staged**: retirar control manual de `es_padre` de contratos canonicos solo mediante transicion documentada. La categoria principal final sera `Producto.categoria_principal_id`, no `es_principal` en el puente.
- Planificar, pero NO activar en estas entregas, el corte de Producto a la FK directa, el CHECK para activos, la retirada del puente ni el alta/edicion atomica del formulario.

## Capabilities

### New Capabilities

- `catalog-integrity-transition`: preflight, constraints y fronteras de despliegue compatibles, sin migraciones destructivas.
- `catalog-category-hierarchy`: arbol, hojas seleccionables, jerarquia derivada, B3 y reactivacion historica.
- `canonical-category-attributes`: identidad canonica, resolver efectivo, overrides, defaults explicitos, bajas diferenciadas y guard de completitud.
- `attribute-measurement-units`: unidades globales protegidas, anotacion semantica y ciclo de vida reversible.

### Modified Capabilities

Ninguna spec principal existe actualmente en `openspec/specs`. Se reutiliza la implementacion de `manage-reversible-attribute-lifecycle`, sin archivarla, alterar sus tareas ni declarar completados sus pendientes. Los requisitos nuevos prevalecen para backfill opt-in y defaults; la evidencia pendiente se integra en las tareas de este cambio.

## Impact

- Coordinacion: mismo nombre de cambio en `osiris-facturacion-fe`; design y specs de ambos repos deben compartir rutas, errores, limites de fase y precondiciones.
- Backend: categoria, atributo, categoria_atributo, resolver EAV existente, nuevo modulo comun unidad, auth/permisos, auditoria, API/docs, preflight y futuras revisiones Alembic aditivas.
- Alcance global: Producto, Categoria, Atributo y Unidad permanecen globales; no agregar empresa_id aislado. Permisos globales deben comprobarse en servidor.
- Inventario: cambios de clasificacion B3 y metadatos auditados; no modificar cantidades, costos ni movimientos. Cartera, SRI y documentos de compra/venta historicos no se recalculan.
- No objetivos: implementar Producto atomico (entrega 7), E2E integral de Producto/retirada legacy (entrega 8), unidad comercial, conversiones, variantes, empaques, remediacion persistente, inferencia de unidades o fusion automatica de duplicados.
- Esta solicitud crea exclusivamente artefactos OpenSpec. No ejecuta preflight sobre datos reales, codigo, seeds, migraciones ni cambios de configuracion de runtime.