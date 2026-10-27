## 1. Gate 7.1 — Contratos coordinados

- [x] 1.1 Documentar contrato integral, errores canónicos, semántica omitido/null/default y compatibilidad temporal en propuesta/spec.
- [x] 1.2 Definir autoridad FK, bridge, estrategia de locks, rollback y secuencia de migración en el diseño.
- [x] 1.3 Alinear payload/respuesta/preview con la especificación frontend `product-integral`.
- [x] 1.4 Validar ambos cambios con OpenSpec estricto y resolver cualquier diferencia contractual antes de schema.

## 2. Gate 7.2 — Preflight y migración aditiva

- [x] 2.1 Extender `audit_catalog_integrity.py --product-cutover` para clasificación, EAV, backfill candidatos y divergencias FK/bridge; coordinar su salida con la auditoría fiscal de scope existente.
- [ ] 2.2 Agregar `categoria_principal_id` nullable, FK e índice mediante migración Alembic sin alterar/eliminar el bridge ni activar restricción final.
- [ ] 2.3 Backfillear solo relación legacy única y válida; reportar y bloquear toda ambigüedad sin escoger categoría.
- [ ] 2.4 Probar upgrade/downgrade/upgrade y fixtures de conflicto en schema PostgreSQL aislado; registrar conteos y diagnóstico.

## 3. Gate 7.3 — Escritura integral

- [ ] 3.1 Definir DTOs canónicos de alta/edición con `categoria_principal_id`, impuestos y EAV tipado; rechazar payloads inválidos/atributos no aplicables.
- [ ] 3.2 Implementar alta atómica con actor autenticado, validación de categoría/atributos/impuestos y una única transacción exterior.
- [ ] 3.3 Implementar edición atómica, semántica de omitido/null, sincronía del bridge y conservación del historial EAV.
- [ ] 3.4 Sustituir guards por roles en operaciones canónicas con permisos efectivos `PRODUCTOS`; hacer que servicios hijos no confirmen la transacción.
- [ ] 3.5 Probar rollback completo en fallos de EAV, impuestos, bridge y auditoría.

## 4. Gate 7.4 — Preview de cambio de categoría

- [ ] 4.1 Implementar preview firmado por operación, actor, producto, categoría destino, payload, estado y expiración.
- [ ] 4.2 Reportar valores conservados/desactivados, defaults explícitos, nuevos obligatorios y faltantes sin persistir.
- [ ] 4.3 Confirmar bajo locks compartidos, validar token/estado de nuevo y desactivar EAV no aplicable sin borrar historia.
- [ ] 4.4 Probar 409 stale, preview faltante, cambios concurrentes de catálogo y rollback total.

## 5. Gate 7.5 — Lectura canónica

- [ ] 5.1 Alinear detalle/listado con categoría principal y ruta, atributos efectivos por UUID con unidad/origen/metadatos, impuestos y bodegas.
- [ ] 5.2 Eliminar excepciones silenciosas en resolución crítica y exponer errores diagnósticos estables.
- [ ] 5.3 Verificar OpenAPI y contratos de respuesta con pruebas BE/FE.

## 6. Gate 7.7 — Cutover de autoridad

- [ ] 6.1 Ejecutar preflight en el entorno objetivo y resolver manualmente todos los conflictos accionables.
- [ ] 6.2 Activar lectura FK y escritura única sincronizada; medir/validar que no existan divergencias bridge.
- [ ] 6.3 Tras pruebas FE/E2E, rechazar múltiples `categoria_ids`, retirar fallback y activar restricción de producto activo con categoría.
- [ ] 6.4 Retirar bridge y GET legacy únicamente cuando inventario de consumidores y postflight confirmen cero usos.

## 7. Gate 7.8 — Verificación y cierre

- [ ] 7.1 Cubrir alta/edición/preview con PostgreSQL, permisos, rollback, concurrencia y auditoría.
- [ ] 7.2 Ejecutar suite BE completa, Ruff, mypy y pruebas PostgreSQL de migración/concurrencia.
- [ ] 7.3 Ejecutar E2E real con productos activos y limpiar fixture por UUID restaurando conteos.
- [ ] 7.4 Actualizar documentación/runbook/evidencia; verificar que no cambió stock, kardex, compras, ventas, cartera, SRI ni documentos.
