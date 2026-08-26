---
id: procesos-reporteria-control-gerencial
title: "07. Reportería y Control Gerencial"
sidebar_position: 8
---

# 07. Reportería y Control Gerencial

## CU060: Monitorear desempeño de ventas

**Actores:** Gerente Comercial, Supervisor de Ventas.

**Descripción:** Obtener visión de ventas agregadas, tendencias y productividad por vendedor.

**Precondiciones:**

- Ventas emitidas en el período.

**Flujo de Eventos Básico:**

1. Consultar resumen de ventas por rango.
2. Consultar tendencias por agrupación (`DIARIA`, `MENSUAL`, `ANUAL`).
3. Consultar rendimiento por vendedor.
4. Consultar top productos y rentabilidad.

**Flujos Alternativos:**

- Sin datos en período: respuesta vacía sin error.

**Postcondiciones:**

- Indicadores comerciales listos para toma de decisiones.

**APIs involucradas:**

- `GET /api/v1/reportes/ventas/resumen` ([doc API](../api/reportes/ventas-y-rentabilidad))
- `GET /api/v1/reportes/ventas/tendencias` ([doc API](../api/reportes/ventas-y-rentabilidad))
- `GET /api/v1/reportes/ventas/por-vendedor` ([doc API](../api/reportes/ventas-y-rentabilidad))
- `GET /api/v1/reportes/ventas/top-productos` ([doc API](../api/reportes/ventas-y-rentabilidad))
- `GET /api/v1/reportes/rentabilidad/por-cliente` ([doc API](../api/reportes/ventas-y-rentabilidad))
- `GET /api/v1/reportes/rentabilidad/transacciones` ([doc API](../api/reportes/ventas-y-rentabilidad))

---

## CU061: Consolidar información tributaria mensual (Pre-104)

**Actores:** Contador, Administrador.

**Descripción:** Consolidar ventas, compras y retenciones para soporte de declaración mensual.

**Precondiciones:**

- Documentos del mes registrados.

**Flujo de Eventos Básico:**

1. Consultar reporte tributario mensual por mes/año.
2. Revisar bloque de ventas (IVA percibido).
3. Revisar bloque de compras (crédito tributario).
4. Revisar retenciones emitidas y recibidas.

**Flujos Alternativos:**

- Mes sin transacciones: valores en cero.

**Postcondiciones:**

- Resumen tributario disponible para trabajo contable.

**APIs involucradas:**

- `GET /api/v1/reportes/impuestos/mensual` ([doc API](../api/reportes/operativos-tributarios))

---

## CU062: Controlar inventario y patrimonio

**Actores:** Gerencia, Encargado de Almacén.

**Descripción:** Monitorear valor del inventario y trazabilidad histórica de movimientos.

**Precondiciones:**

- Movimientos de inventario registrados.

**Flujo de Eventos Básico:**

1. Consultar valoración de inventario.
2. Consultar kardex histórico por producto y rango de fechas.

**Flujos Alternativos:**

- Producto sin movimientos: historial vacío.

**Postcondiciones:**

- Visibilidad de stock valorizado y trazabilidad NIIF.

**APIs involucradas:**

- `GET /api/v1/reportes/inventario/valoracion` ([doc API](../api/reportes/operativos-tributarios))
- `GET /api/v1/reportes/inventario/kardex/{producto_id}` ([doc API](../api/reportes/operativos-tributarios))

---

## CU063: Gestionar liquidez (cartera y caja)

**Actores:** Gerencia Financiera, Tesorería.

**Descripción:** Controlar quién debe y a quién se debe, y validar cierre diario por forma de pago.

**Precondiciones:**

- CxC/CxP con movimientos.
- Pagos registrados en día operativo.

**Flujo de Eventos Básico:**

1. Consultar cartera por cobrar por cliente.
2. Consultar cartera por pagar por proveedor.
3. Ejecutar cierre diario de caja.

**Flujos Alternativos:**

- Sin pagos en fecha: cierre devuelve montos en cero.

**Postcondiciones:**

- Estado de liquidez consolidado para control gerencial.

**APIs involucradas:**

- `GET /api/v1/reportes/cartera/cobrar` ([doc API](../api/reportes/operativos-tributarios))
- `GET /api/v1/reportes/cartera/pagar` ([doc API](../api/reportes/operativos-tributarios))
- `GET /api/v1/reportes/caja/cierre-diario` ([doc API](../api/reportes/operativos-tributarios))

---

## CU064: Monitorear salud de facturación electrónica

**Actores:** Administrador, Supervisor de Facturación.

**Descripción:** Identificar documentos en cola, autorizados o rechazados para continuidad operativa.

**Precondiciones:**

- Documentos electrónicos generados.

**Flujo de Eventos Básico:**

1. Consultar monitor de estados SRI por período.
2. Identificar documentos rechazados o en cola.
3. Coordinar acciones correctivas operativas.

**Flujos Alternativos:**

- Sin actividad FE: resultados con conteos en cero.

**Postcondiciones:**

- Estado FE visible para gestión de contingencia.

**APIs involucradas:**

- `GET /api/v1/reportes/sri/monitor-estados` ([doc API](../api/reportes/operativos-tributarios))
- `GET /api/v1/fe/cola` ([doc API](../api/sri/facturacion-electronica-cola-documentos))

