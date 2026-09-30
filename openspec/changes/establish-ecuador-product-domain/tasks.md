## 1. Línea Base y Contratos

- [ ] 1.1 Añadir pruebas de contrato para los recorridos canónicos de organización, catálogo, inventario, compras, ventas y documentos SRI.
- [ ] 1.2 Inventariar rutas heredadas y consumidores antes de definir su deprecación.
- [ ] 1.3 Documentar variables, certificados y dependencia FE-EC por ambiente.

## 2. Organización y Seguridad

- [ ] 2.1 Finalizar campos tributarios canónicos de empresa y su migración Alembic.
- [ ] 2.2 Verificar reglas de régimen, resoluciones, sucursales, puntos de emisión y secuenciales.
- [ ] 2.3 Cubrir aislamiento por empresa y autorización de operaciones sensibles.

## 3. Inventario y Operaciones Comerciales

- [ ] 3.1 Verificar atomicidad e idempotencia de compra, ingreso, CxP y anulación.
- [ ] 3.2 Verificar atomicidad e idempotencia de venta, egreso, CxC y anulación.
- [ ] 3.3 Formalizar tipos directos de inventario y evitar documentos comerciales duplicados.
- [ ] 3.4 Cubrir stock insuficiente, reversos y consistencia stock/kárdex/costo promedio.

## 4. Facturación Electrónica Ecuador

- [ ] 4.1 Sustituir la autorización mock implícita por un modo de prueba explícito y fallo cerrado en producción.
- [ ] 4.2 Verificar firma, recepción, autorización, reintentos e historial con la rueda FE-EC desplegada.
- [ ] 4.3 Verificar XML, RIDE A4, ticket, correo y permisos de descarga.
- [ ] 4.4 Resolver y especificar el alcance de notas de crédito y débito.

## 5. Reportes y Calidad

- [ ] 5.1 Verificar que reportes usen documentos y movimientos canónicos con alcance de empresa.
- [ ] 5.2 Ejecutar migraciones sobre una copia de datos y comprobar rollback.
- [ ] 5.3 Ejecutar `poetry run pytest`, Ruff y mypy y resolver solo regresiones del cambio.