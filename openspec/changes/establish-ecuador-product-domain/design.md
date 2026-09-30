## Context

FastAPI, SQLModel/SQLAlchemy y Alembic soportan un dominio modular. Compras y ventas ya orquestan `MovimientoInventarioService`; facturación usa FE-EC, una cola persistida y servicios de documentos. El cambio debe formalizar y endurecer estos contratos sin una reescritura.

## Goals / Non-Goals

**Goals:**
- Consolidar servicios canónicos y transacciones atómicas.
- Asegurar aislamiento por empresa, auditoría e historial.
- Separar claramente modos SRI reales y de prueba.
- Mantener compatibilidad mediante migraciones Alembic.

**Non-Goals:**
- Introducir contabilidad de doble partida.
- Cambiar sesiones síncronas o el framework.
- Ejecutar `metadata.create_all()`.

## Decisions

### Decision: Movimiento de inventario como libro operativo
Compras y ventas seguirán creando movimientos referenciados (`COMPRA:<id>`, `VENTA:<id>`). Stock y kárdex se actualizarán solo al confirmar movimientos dentro de la transacción comercial.

### Decision: Contratos canónicos bajo `/api/v1`
Los endpoints canónicos conservarán servicios y DTOs por dominio. Las rutas heredadas tendrán una migración explícita antes de retirarse.

### Decision: Fallo cerrado en producción SRI
El modo mock solo estará permitido por configuración explícita de desarrollo/pruebas. Producción fallará si firma, certificado o transporte no están disponibles.

### Decision: Snapshots tributarios
Los documentos emitidos conservarán los valores usados para cálculo y representación, aunque cambie el catálogo posteriormente.

## Risks / Trade-offs

- Rutas heredadas consumidas por frontend -> inventariar llamadas y migrarlas antes de deprecar.
- Reversos con stock ya consumido -> rechazar y requerir resolución operativa explícita.
- Integración FE-EC local -> probar la rueda exacta y documentar su despliegue.
- Cambios tributarios normativos -> versionar catálogos y evitar constantes de UI como autoridad.

## Migration Plan

1. Documentar y probar contratos canónicos existentes.
2. Completar configuración tributaria y migraciones pendientes.
3. Endurecer el modo SRI por ambiente.
4. Migrar consumidores frontend de rutas duplicadas.
5. Deprecar contratos heredados con una ventana explícita.

Rollback: mantener migraciones reversibles y conservar rutas heredadas hasta verificar consumidores; desactivar nuevas rutas mediante despliegue anterior sin borrar datos.

## Open Questions

- Alcance normativo de notas de crédito y débito en el primer lanzamiento.
- Política definitiva para anulaciones después de cierres operativos.
- Estrategia de renovación y custodia del certificado de firma.