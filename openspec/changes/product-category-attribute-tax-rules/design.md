## Context

El backend ya implementa parte del dominio: `Producto.tipo` admite `BIEN/SERVICIO`; `ProductoImpuesto` permite varias filas; el catálogo tiene `aplica_a`; `Empresa.impuesto_catalogo_ids` conserva la selección tributaria; las categorías tienen `parent_id`, ciclo detectado al mover, categoría hoja para productos y la regla B3 que mueve productos existentes a una subcategoría `General`; los atributos se heredan por CTE y sus valores se almacenan tipados.

Los contratos no están alineados entre sí:

- La ruta `/productos` usa `pages/ProductosPage.tsx`, que envía un solo `impuesto_id` y lo convierte en una lista de un elemento. `/products` monta otro formulario, con EAV/fotos, pero no declara ni transmite impuestos.
- `ProductoUpdate` no acepta `impuesto_catalogo_ids`; el servicio solo trata esa lista durante la creación.
- `ProductoImpuesto` no incluye empresa. Se lee por `producto_id` en los detalles, compras y snapshots de venta, aunque un producto puede asignarse a bodegas de varias empresas.
- `_validate_impuestos` verifica catálogo activo y `aplica_a`, pero no pertenencia a `Empresa.impuesto_catalogo_ids` ni vigencia. Una lista vacía evita la llamada al validador. La ruta de asignación individual verifica vigencia, pero reemplaza una asignación del mismo tipo de impuesto.
- La definición de `Atributo` solo tiene `string`, `integer`, `decimal`, `boolean` y `date`, además de una unicidad global por nombre. El detalle de negocio también requiere opciones/catalog, obligatoriedad heredada, unicidad por rama y remapeos.
- El documento de reglas marca sus discrepancias como gaps *as-is*. No todas son decisiones funcionales aprobadas para facturación.

La `Empresa` es el origen de los IDs tributarios permitidos. La empresa activa debe resolverse mediante el scope autenticado del backend; un `empresa_id` enviado por navegador no es autoridad. El cambio afecta inventario, contratos SRI, compras, ventas y multiempresa.

El frontend no manda un `X-Company` explícito. El formulario canónico debe obtener los impuestos configurados de la empresa activa mediante un endpoint/contexto autenticado; si no puede determinar la empresa, no debe mostrar el catálogo global como alternativa. El backend revalida siempre el scope.

La regla B3 de `CategoriaService` crea automáticamente una subcategoría `General` cuando una categoría con productos directos recibe su primer hijo; luego mueve allí esos productos. La nueva subcategoría temporal debe llamarse `Sin clasificar` y conservar como padre la categoría original: si `Laptops` se crea bajo `Computadoras`, `Sin clasificar` también es hija de `Computadoras`, hermana de `Laptops`, y recibe los productos que estaban asignados directamente a `Computadoras`. Nunca debe quedar debajo de `Laptops`. “Legacy General” se refiere a esos buckets B3 históricos. Como la tabla no guarda un marcador de origen, puede haber categorías manuales con el mismo nombre: no se deben renombrar/marcar solo por llamarse `General`.

## Goals / Non-Goals

**Goals:**
- Unificar el alta/edición/listado visible de productos en un solo formulario y normalizar todas las rutas de interfaz al español, sin mantener páginas paralelas en inglés.
- Hacer explícitos y validables el tipo de producto, categorías hoja y atributos heredados según las reglas de negocio acordadas.
- Permitir seleccionar uno o más impuestos compatibles que estén configurados y vigentes para la empresa activa.
- Evitar contaminación tributaria entre empresas cuando un mismo producto global está asociado a bodegas de distintos tenants.
- Usar el perfil fiscal de la empresa en detalles, compras y ventas, y mantener inmutables los snapshots de documentos ya creados.
- Migrar relaciones actuales con reporte de filas ambiguas, sin descartar asignaciones ni inferir una empresa arbitrariamente.

**Non-Goals:**
- Rediseñar la fórmula legal de IVA/ICE o el XML SRI más allá de consumir el perfil de impuestos validado.
- Crear contabilidad de doble partida, proveedores, precios por empresa o servicios de catálogo separados.
- Cambiar `Producto` a una entidad duplicada por empresa en este cambio; se mantiene identidad global y se contextualiza solo el perfil tributario.
- Aplicar automáticamente las 22 observaciones del documento *as-is* sin especificar su comportamiento objetivo y sus casos de migración.

## Decisions

1. **Un perfil tributario por empresa y producto.** Añadir empresa a la relación tributaria (o tabla equivalente con unicidad empresa/producto/impuesto); no añadir empresa a `Producto`, que sigue siendo compartido. En requests, empresa viene del contexto autenticado. Una misma mercancía puede requerir IVA distinto en dos empresas.
2. **IVA 0% predeterminado en empresa.** Si la lista empresarial no contiene ningún IVA al crear o guardar configuración, agregar el registro activo y vigente del catálogo con porcentaje cero. Normalizar también empresas existentes en la migración. Resolverlo por tipo/tasa, no por UUID constante; fallar con diagnóstico si el catálogo no contiene exactamente un registro canónico.
3. **Perfil de impuestos de producto limitado a IVA/ICE.** Create requiere lista no vacía con exactamente un IVA; ICE es opcional, y solo puede haber una asignación activa de cada tipo. Se validan empresa configurada, vigencia, actividad y `aplica_a` frente a `BIEN/SERVICIO`. IRBPNR no se ofrece ni se asigna a productos en este alcance. Update reemplaza el set completo solo cuando la lista se incluye, en la misma transacción.
4. **Rutas españolas en toda la interfaz.** Elegir español porque es el idioma dominante actual. Normalizar rutas, menús, enlaces, navegación y pruebas a paths españoles; las rutas inglesas existentes serán redirects temporales hacia la ruta española equivalente, no implementaciones paralelas. `/productos` queda como única implementación canónica del catálogo.

	Mapa inicial de rutas inglesas: `/login` → `/iniciar-sesion`; `/change-password` → `/cambiar-contrasena`; `/inventory/*` → `/inventario/*`; `/categories` → `/categorias`; `/products` → `/productos`; `/products/new` → `/productos?accion=nuevo`; `/products/:id` → `/productos?detalle=:id`; `/products/:id/edit` → `/productos?editar=:id`; `/suppliers` → `/proveedores`; `/customers` → `/clientes`; `/recategorize` → `/recategorizar`; `/remap` → `/remapeos`; `/catalogs` → `/catalogos`; `/reports/*` → `/reportes/resumen/*`; `/audit` → `/auditoria`; `/admin/users` → `/admin/usuarios`; `/admin/params` → `/admin/parametros`; `/403` → `/prohibido`. El inventario de código completa rutas no listadas antes de migrarlas.
5. **Compras y ventas resuelven por empresa.** Hidratación de producto y snapshots reciben el `empresa_id` ya resuelto. No consultan ni mezclan relaciones de otras empresas. Una vez copiados a las líneas/comprobantes, los datos tributarios son históricos e inmutables.
6. **Categoría default marcada, no inferida por nombre.** Añadir `is_default` para nuevas categorías temporales `Sin clasificar`. Al agregar el primer hijo a una categoría con productos directos, crear/reutilizar `Sin clasificar` como otro hijo del mismo padre y mover allí los productos directos en la misma transacción. No colocarla dentro del nuevo hijo. “General” es el bucket automático que B3 generaba; no todos los `General` históricos son necesariamente automáticos. Generar reporte y marcar/renombrar solo candidatos estructuralmente verificables. La categoría temporal no acepta productos finales y se desactiva al quedar vacía.
7. **Recategorización obligatoria y visible.** Publicar un conteo empresarial de productos activos en categorías `is_default` en el layout autenticado. Mientras sea mayor que cero, mostrar la banda persistente `Hay {N} producto(s) sin recategorizar en categorías "Sin clasificar". Recategorizar ahora` enlazada a `/recategorizar`; ocultarla al llegar a cero. La banda dirige al flujo de recategorización existente y no cambia stock ni perfiles tributarios.
8. **Atributos configurables por rama y defaults tipados vigentes.** Mantener herencia más específica, ampliar tipos con `select` y `catalog`, almacenar opciones/referencia a catálogo, y validar aplicabilidad y obligatoriedad en backend al persistir. Reemplazar unicidad global del nombre por detección de duplicados en la rama efectiva. Conservar los defaults tipados actuales (`N/A`, `0`, `0.00`, `false` o la fecha actual según tipo) y asegurar que se guarden en el campo tipado correspondiente.
9. **Movimiento de categorías conserva datos por defecto.** Bloquear ciclos, exigir padre activo y destino hoja para productos. Solo si el movimiento produce colisión heredada puede el usuario confirmar la limpieza de valores afectados; la interfaz no envía un flag destructivo en movimientos ordinarios.
10. **Migración bloqueante con reporte.** Primero enumerar relaciones `ProductoImpuesto` y empresas inferidas desde `ProductoBodega -> Bodega.empresa_id`. Si una relación no tiene empresa inferible, o la empresa no tiene configurado el impuesto, abortar upgrade con IDs y comando de reconciliación. Backfill automático solo se hace cuando el mapeo es unívoco y compatible; preservar auditoría y permitir downgrade antes de uso de nuevos perfiles.

## Risks / Trade-offs

- [Relaciones tributarias legacy sin empresa o no permitidas por la empresa] → la migración no reasigna relaciones ni agrega sus impuestos a la whitelist; emite reporte y bloquea upgrade si quedan asignaciones activas sin conciliar. La auditoría inicial development del 2026-10-02 encontró 24 relaciones fuera de whitelist; los 19 productos de prueba y las 24 asignaciones quedaron inactivos y se conservan sin empresa. Al aplicar 2.2 se añadió solo el IVA 0% canónico vigente requerido para empresas existentes sin IVA; la preflight valida asignaciones activas.
- [Mismo producto tiene perfiles distintos] → el servicio y todos sus lectores deben pasar empresa; añadir pruebas que prueben aislamiento A/B y no usar fallback silencioso a perfil global.
- [Cambiar impuestos tras ventas existentes] → los documentos usan snapshots y no vuelven a calcularse.
- [Cambio de tipo con impuestos existentes] → validar compatibilidad antes de persistir; actualización tipo+taxes es una transacción.
- [Categorías `General` existentes no son todas temporales] → reporte estructural; no clasificar solo por nombre, e intervenir manualmente los casos ambiguos.
- [IVA 0% ausente o duplicado en el catálogo] → validar el seed antes del cambio y no elegir una fila arbitraria.
- [Rutas inglesas externas] → redirigir a rutas españolas canónicas y comprobar enlaces/recarga directa antes de retirar páginas duplicadas.

## Migration Plan

1. Inventariar productos, bodegas, empresas, impuestos y perfiles existentes; producir reporte de relaciones sin empresa o con impuesto no configurado/vigente.
2. Resolver casos ambiguos; generar Alembic para perfil empresa/producto, unicidad/índices y `is_default` en categoría. Preparar también columnas/almacenamiento para `select/catalog` y agregar IVA 0% a las configuraciones de empresa existentes que no tengan IVA.
3. Backfill relaciones solo con mapeo determinista; validar que no se pierden IDs ni snapshots. Ejecutar upgrade/downgrade sobre SQLite de pruebas y PostgreSQL con copia representativa.
4. Desplegar lectura/escritura tributaria contextual en catálogo, compras y ventas; migrar consumidores y mantener alias de rutas.
5. Desplegar formulario unificado y habilitar selección múltiple basada en configuración de empresa.
6. Revisar pendientes de remapeo, perfiles fiscales y candidatos `General` antes de activar el flujo productivo.
7. Cambiar navegación y rutas a español; validar redirects heredados, recarga directa y ausencia de dos formularios para productos.

Rollback: volver al artefacto anterior mientras los nuevos perfiles no se hayan usado para emitir documentos. Después de uso, conservar columnas y perfiles; no borrar ni mezclar asignaciones tributarias automáticamente.

## Open Questions

No quedan decisiones funcionales bloqueantes. Antes de ejecutar el upgrade en development/producción se debe completar la conciliación manual del reporte fiscal. La auditoría no cambió datos.
