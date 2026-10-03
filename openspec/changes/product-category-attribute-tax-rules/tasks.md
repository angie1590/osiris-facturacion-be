## 1. Decisiones y contratos

- [x] 1.1 Implementar IVA 0% por defecto en empresa cuando no se seleccione IVA; limitar perfil de producto a IVA/ICE y preservar defaults tipados actuales.
- [x] 1.2 Inventariar las rutas del frontend, migrar menús/enlaces a paths españoles y redirigir las rutas inglesas heredadas a un único destino español; probar carga directa y bookmarks.
- [x] 1.3 Añadir pruebas de contrato para BIEN/SERVICIO, configuración tributaria empresarial, atributos heredados y operaciones de categoría.

## 2. Modelo multiempresa y migraciones

- [x] 2.1 Crear auditoría de `ProductoImpuesto` legacy: inferir empresas desde bodegas, detectar perfiles ambiguos, impuestos no configurados y productos sin empresa resoluble.

> Auditoría inicial (`development`, 2026-10-02): una empresa tenía la whitelist vacía y 24 asignaciones activas (IVA código SRI 0: 1, IVA 4: 18, ICE 3011: 5), todas `TAX_NOT_CONFIGURED_FOR_COMPANY`. Tras confirmación de que los productos eran de prueba, se dieron de baja lógicamente los 19 productos y se inactivaron sus 24 asignaciones, sin reasignarlas. Al aplicar la migración a development se añadió únicamente el IVA 0% canónico vigente, requisito de 2.2; no se añadieron los otros impuestos legacy. Estado actual: 0 asignaciones fiscales activas; las 24 filas inactivas se conservan sin `empresa_id`.

- [x] 2.2 Diseñar y crear migración Alembic para perfil de impuestos por empresa/producto, unicidad/índices y backfill solo de relaciones conciliadas; agregar IVA 0% a empresas existentes sin IVA; abortar con reporte accionable si hay relaciones pendientes de conciliación.

> Probada en SQLite con bloqueo de legacy no configurado y backfill de una relación conciliada, e integrada en roundtrip PostgreSQL 15. Aplicada a development: la única whitelist empresarial recibió el IVA 0% canónico y las 24 asignaciones legacy inactivas se conservaron sin reasignación.
- [x] 2.3 Añadir `is_default` a categoría; documentar que `General` es la subcategoría automática de la regla B3 que recibe productos al crear el primer hijo y migrar solo candidatos verificables, no por nombre a ciegas.

> La revisión lista candidatos legacy `General` con productos para revisión, pero no los marca automáticamente porque el esquema histórico no conserva el origen B3.
- [x] 2.4 Ampliar el modelo de atributos para `select`/`catalog`, opciones/referencia de catálogo y restricciones configurables; preparar migración de unicidad global a unicidad por rama.
- [x] 2.5 Probar upgrade/downgrade y compatibilidad PostgreSQL/SQLite; cubrir conciliación de datos legacy y preservar snapshots históricos.

> Roundtrip PostgreSQL 15 aislado: upgrade completo hasta `d6f9a3c18b50`, downgrade a `f61a8d3c2b90` y re-upgrade a head. En SQLite pasaron las pruebas de bloqueo/backfill legacy, default IVA, categorías, atributos, remapeos y snapshots históricos. En development, Alembic quedó en `d6f9a3c18b50`; los 19 productos siguen inactivos y se preservan documentos/snapshots.

## 3. Producto e impuestos

- [x] 3.1 Mantener BIEN/SERVICIO en create/update y validar taxes existentes al cambiar tipo.
- [x] 3.2 Centralizar la resolución del perfil fiscal por empresa autenticada; rechazar operaciones tributarias sin contexto empresarial cuando no sea unívoco.
- [x] 3.3 Filtrar catálogo seleccionable a IVA/ICE configurados por empresa, activos, vigentes y compatibles con `aplica_a`; el IVA 0% garantiza una opción aunque la empresa no haya elegido IVA.
- [x] 3.4 Hacer que create exija exactamente un IVA y permita ICE opcional; update reemplaza la lista de forma atómica y rechaza duplicados, lista vacía o IRBPNR.
- [x] 3.5 Aplicar el mismo alcance empresarial en endpoints de asignación/listado/baja de impuestos de producto.
- [x] 3.6 Actualizar hidratación de compras y ventas para consultar perfil empresa/producto y snapshotearlo en la transacción; impedir mezcla de empresas y mantener documentos pasados inmutables.

## 4. Categorías y atributos

- [x] 4.1 Hacer coherentes parent/child para nodos intermedios; validar padre activo, autorreferencia/ciclos y asignación de productos solo a categorías hoja y no temporales.
- [x] 4.2 Implementar `Sin clasificar` como hija del padre original y hermana del nuevo hijo; mover productos directos atómicamente y desactivarla al quedar vacía.
- [x] 4.3 Implementar reglas de baja lógica: bloquear hijos activos/stock positivo y exigir confirmación para baja en cascada de productos sin stock.
- [x] 4.4 Validar duplicados de atributos en la rama efectiva, permitir nombres iguales en ramas independientes y preservar herencia con precedencia más específica.
- [x] 4.5 Validar en backend atributos requeridos, no vacíos según política acordada, tipos, select/options, catálogo y negativos; aplicar reglas en create/update y upsert de valores.
- [x] 4.6 Completar migración de tipo de atributo: convertir valores válidos y registrar valores no convertibles en remapeo auditable.
- [x] 4.7 Limpiar valores de atributos al mover categorías solo ante una colisión real y confirmación explícita; auditar antes/después y no borrar por cambios ordinarios.

## 5. Frontend canónico

- [x] 5.1 Consolidar listado/formulario bajo `/productos` en `osiris-facturacion-fe`; normalizar rutas, enlaces y navegación del frontend al español y redirigir rutas inglesas heredadas al destino canónico.
- [x] 5.2 Obtener la lista permitida desde el contexto de la empresa activa; sustituir impuesto único por selector de IVA obligatorio + ICE opcional, filtrado por vigencia y `BIEN/SERVICIO`; mostrar IVA 0% empresarial por defecto.
- [x] 5.3 Permitir editar y reemplazar impuestos del producto con el mismo contrato que create; refrescar detalle y listas al guardar.
- [x] 5.4 Completar selectores `select`/`catalog`, defaults, obligatoriedad y advertencias de remapeo de atributos.
- [x] 5.5 Ajustar categorías temporales `Sin clasificar` (B3/legacy `General`), reglas leaf/parent, confirmación de movimiento destructivo y mensajes de baja según códigos API.
- [x] 5.6 Añadir conteo por empresa y alerta persistente en el layout autenticado con el texto/CTA de recategorización; ocultarla al quedar en cero y probar el enlace y el contador.

## 6. Seguridad y verificación

- [x] 6.1 Aplicar matriz RBAC acordada y auditoría a cambios de producto, perfil fiscal, categoría, atributo y remapeo.
- [x] 6.2 Añadir pruebas de aislamiento empresa A/B, no configurado, expirado, incompatible, duplicado, lista vacía, rollback y snapshots de compras/ventas.
- [x] 6.3 Añadir pruebas de categorías/atributos para ciclo, leaf, temporal, cascada, herencia, required/select/catalog y conversión de tipo.
- [x] 6.4 Ejecutar suites backend/frontend, Ruff, MyPy focalizado, ESLint, build y migración PostgreSQL/SQLite; actualizar documentación de contrato y conciliación legacy.

> Verificación final: backend 503 passed, 1 skipped; frontend 90 passed. Ruff, ESLint, TypeScript/build y docs-audit (204/204) pasan. MyPy strict focalizado pasó en 26 archivos con `--explicit-package-bases`; se limita el import-untyped a `jose`, que no distribuye stubs. Upgrade, downgrade y re-upgrade de las cuatro revisiones del change pasaron en PostgreSQL 15 aislado; las pruebas SQLite de conciliación/backfill y snapshots también pasan. `make test` intenta migrar development, así que se ejecutó pytest directamente. No se aplicaron migraciones a development.
