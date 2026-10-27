## Context

El producto actual persiste clasificación solo en `tbl_producto_categoria`; `ProductoCreate/Update` aceptan `categoria_ids`, las rutas mutables usan nombres de rol y el servicio guarda impuestos/EAV en suboperaciones. `get_producto_completo` reconstruye varias relaciones desde el bridge y actualmente puede convertir errores de resolución EAV en una respuesta vacía. La entrega requiere cambios coordinados de modelo, API, permisos, migración y UI.

Restricciones: FastAPI síncrono con SQLModel/PostgreSQL; toda evolución de schema es Alembic; los servicios internos deben respetar una transacción exterior (`commit=False`); categorías/atributos permanecen globales y el perfil tributario continúa sujeto al contexto de empresa autenticado existente. No se toca stock, kardex, compras, ventas, cartera, SRI ni documentos.

## Goals / Non-Goals

**Goals:**
- Establecer `Producto.categoria_principal_id` como autoridad y la tabla puente solo como proyección temporal.
- Dar alta/edición integral y cambio de categoría con preflight/preview, valores EAV tipados, impuestos y auditoría atómicos.
- Preservar datos e historia y bloquear ambigüedades en lugar de inferir decisiones de negocio.
- Permitir despliegue gradual con lectura compatible temporal y cutover comprobable.

**Non-Goals:**
- Cambiar reglas fiscales o alcance multiempresa del catálogo.
- Hacer categorías secundarias funcionales, variantes, importación masiva o nuevas reglas de stock.
- Migrar relaciones tributarias fuera del perfil actualmente resuelto.
- Modificar código persistido durante el Gate 7.1.

## Decisions

1. **FK directo como autoridad, puente como proyección.** Añadir FK nullable e índice en fase aditiva. Mientras existan consumidores, el servicio integral escribe FK y sincroniza una sola fila bridge en la misma transacción; ningún escritor independiente puede cambiar solo el bridge. Las lecturas nuevas usan el FK. Se eligió frente a mantener dos autoridades porque no permite establecer una clasificación unívoca. El bridge se elimina únicamente después del inventario de consumidores y postflight.

2. **Backfill solo determinista.** El conjunto de preflights READ ONLY combina `audit_catalog_integrity.py --product-cutover` (clasificación, EAV, remapeos y FK/bridge cuando exista) con `audit_product_tax_company_scope.py` (scope, vigencia, whitelist y compatibilidad tributaria existentes). Solo una relación legacy única y válida se copia al FK. Los demás casos se bloquean y se presentan con ID y ruta legible; no se selecciona la primera fila ni se asigna un default.

3. **Contrato integral en rutas Producto existentes.** `POST /api/v1/productos` y `PUT /api/v1/productos/{id}` aceptan la categoría principal, impuestos y un conjunto de `{atributo_id, valor}`. El actor y empresa vienen del contexto autenticado. `categoria_ids` se conserva como entrada de transición con detección de conflicto y deprecación; no es aceptado por el cliente canónico. La retirada/rechazo definitivo ocurre solo en el gate de cutover.

4. **Una transacción exterior.** Router valida autorización y delega a una unidad de trabajo de Producto. Servicios de producto, bridge, impuestos, EAV y auditoría no hacen commit interno; cualquier validación o escritura fallida revierte todo. Se usa `commit=False` o una interfaz equivalente ya compatible con los servicios. Se elige esta frontera en lugar de coordinar solicitudes cliente porque elimina estados parcialmente persistidos.

5. **Locks deterministas.** En mutaciones que cambian aplicabilidad, adquirir primero el lock de jerarquía usado por categorías; luego bloquear la fila Producto (`FOR UPDATE` en update), validar categoría y resolver, y modificar relaciones de impuestos/EAV/bridge en orden estable. Preview y confirmación usan la misma base de estado; confirmación vuelve a resolver bajo lock. No se acepta un token solo porque no haya expirado.

6. **Semántica de valores.** Crear acepta solo atributos efectivos; valor omitido/null se satisface únicamente por default explícito cuando sea válido, de lo contrario bloquea un obligatorio. En edición sin cambio de categoría, los atributos omitidos se conservan; `null` desactiva lógicamente solo un opcional y un obligatorio rechaza. Los valores compartidos por `atributo_id` se conservan en cambio de categoría si siguen siendo válidos; los que dejan de aplicar se desactivan sin borrar historia.

7. **Preview firmado y ligado a estado.** `POST /productos/{id}/previsualizar-cambio-categoria` firma/bindea operación, actor, producto, categoría destino, payload relevante, estado/versionado de categoría/atributos/valores y expiración. Responde conservados, desactivados, defaults explícitos, nuevos obligatorios y faltantes. La confirmación integral incluye `precondicion_preview`; se rechaza con `409 CATALOG_PREVIEW_STALE` cualquier diferencia de actor, objetivo, payload o estado. No se persiste un borrador incompleto.

8. **Permisos y actor.** Las operaciones canónicas usan `PRODUCTOS.leer/crear/actualizar/eliminar`; preview usa actualizar. Categoría/atributos/impuestos auxiliares conservan sus propios permisos. `usuario_auditoria` no es autoridad wire: se deriva del usuario autenticado y los eventos de negocio participan de la transacción.

9. **Detalle explícito y errores visibles.** `ProductoCompletoRead` incorpora categoría principal/ruta, atributos efectivos con identidad, origen, unidad y valor tipado, perfil tributario y datos de bodega que el formulario necesita. Errores críticos de resolver no se convierten en arrays vacíos. Contrato de error estable incluye `code`, `message`, `fields`, `conteos` y acciones permitidas cuando aplique.

10. **Compatibilidad con fecha de salida definida por gates.** Se mantiene fallback de lectura solo mientras exista producto histórico sin FK y con métrica/log diagnóstico; se retira al completar preflight/postflight. Se conserva temporalmente GET legacy categoría-atributo para Producto; se elimina tras validar que no tenga consumidores. No se activa NOT NULL ni CHECK final antes del cutover.

## Risks / Trade-offs

- [Datos activos ambiguos impiden migración/cutover] → preflight accionable y resolución humana; migración no selecciona categorías.
- [Lecturas bridge y FK divergen durante despliegue] → escritura sincronizada única, métrica de divergencia y postflight; no abrir escritor paralelo.
- [Locks pueden aumentar latencia o causar deadlocks] → orden compartido con mutaciones de jerarquía y pruebas PostgreSQL de concurrencia.
- [Cambios de catálogo invalidan un preview] → token ligado al estado y respuesta 409; FE conserva borrador y solicita preview nuevo.
- [Contrato tributario actual tiene contexto de empresa] → reutilizar validación existente y no crear una segunda whitelist ni migración fiscal dentro de esta entrega.
- [Hay dos páginas de producto en FE] → `/productos` queda como única implementación y rutas inglesas redirigen; documentar equivalencias y cubrir navegación.

## Migration Plan

1. Completar preflight READ ONLY y respaldar base antes de tocar datos. Gates de especificación no generan migración.
2. Agregar FK nullable, FK/index; ensayar upgrade/downgrade/upgrade en schema PostgreSQL aislado sin eliminar bridge ni activar restricción final.
3. Ejecutar backfill únicamente para filas legacy únicas y válidas. Bloquear cutover mientras exista conflicto; registrar conteos y postflight.
4. Desplegar lectura FK preferente con fallback medido; desplegar escritura integral que sincroniza FK y bridge.
5. Desplegar contrato de detalle, permisos efectivos, preview y UI integral; completar E2E con productos activos.
6. Verificar que todo producto activo tiene FK válido, una sola fila bridge coincidente y todos sus obligatorios/impuestos válidos. Activar restricción final solo entonces.
7. Retirar fallback, payload `categoria_ids`, bridge y GET legacy en commits separados cuando los inventarios de consumidores estén vacíos.

Rollback: antes del cutover, volver al servicio anterior manteniendo FK nullable y bridge. No eliminar FK ni datos backfilleados mientras haya escrituras integrales; primero detenerlas y verificar que no se pierda autoridad/historia. Tras cutover, rollback requiere un plan de datos explícito, nunca reconstrucción automática de categorías ambiguas.

## Open Questions

No hay preguntas funcionales bloqueantes para redactar contratos. Gate 7.2 debe confirmar nombres/mecanismo de versionado del preview y constraints Alembic existentes; cualquier divergencia técnica se actualiza en diseño antes de implementar el gate afectado.
