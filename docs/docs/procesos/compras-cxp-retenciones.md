---
id: procesos-compras-cxp-retenciones
title: "04. Compras, CxP y Retenciones Emitidas"
sidebar_position: 5
---

# 04. Compras, CxP y Retenciones Emitidas

## CU030: Registrar compra de proveedor

**Actores:** Asistente de Compras, Administrador.

**Descripción:** Registrar factura de proveedor y disparar impactos administrativos/operativos.

**Precondiciones:**

- Proveedor activo.
- Bodega activa para ingreso.
- Usuario con permisos de compras.

**Flujo de Eventos Básico:**

1. El actor registra compra (manual o desde catálogo).
2. El sistema calcula bases e impuestos.
3. El sistema registra compra en estado `REGISTRADA`.
4. Se genera ingreso de inventario.
5. Se crea cuenta por pagar inicial (`PENDIENTE`).

**Flujos Alternativos:**

- Secuencial o autorización inválidos: rechazo.
- Bodega no resoluble: rechazo.

**Postcondiciones:**

- Compra registrada, inventario incrementado, CxP creada.

**APIs involucradas:**

- `POST /api/v1/compras` ([doc API](../api/transacciones/compras))
- `POST /api/v1/compras/desde-productos` ([doc API](../api/transacciones/compras))

---

## CU031: Anular compra con reverso operativo

**Actores:** Administrador, Supervisor de Compras.

**Descripción:** Anular compra y revertir su efecto operativo de inventario.

**Precondiciones:**

- Compra existente en estado anulable.
- Motivo de anulación informado.

**Flujo de Eventos Básico:**

1. El actor solicita anulación de compra.
2. El sistema valida reglas de negocio.
3. Cambia estado a `ANULADA`.
4. Ejecuta reverso operativo asociado.

**Flujos Alternativos:**

- Si existen restricciones de estado/flujo, el sistema rechaza anulación.

**Postcondiciones:**

- Compra anulada con trazabilidad de motivo y reverso correspondiente.

**APIs involucradas:**

- `POST /api/v1/compras/{compra_id}/anular` ([doc API](../api/transacciones/compras))

---

## CU032: Sugerir retenciones emitidas por plantilla

**Actores:** Asistente de Compras.

**Descripción:** Automatizar sugerencia de retenciones en base a plantillas y bases imponibles de compra.

**Precondiciones:**

- Compra registrada.
- Plantilla de proveedor disponible (o decisión de guardarla desde operación manual).

**Flujo de Eventos Básico:**

1. El actor consulta sugerencia de retención para una compra.
2. El sistema calcula valores por códigos SRI.
3. El actor confirma/ajusta retención.
4. (Opcional) Guarda la configuración como plantilla por defecto.

**Flujos Alternativos:**

- Sin plantilla disponible: se continúa con carga manual.

**Postcondiciones:**

- Retención sugerida o plantilla guardada para futuros documentos.

**APIs involucradas:**

- `GET /api/v1/compras/{compra_id}/sugerir-retencion` ([doc API](../api/transacciones/compras))
- `POST /api/v1/compras/{compra_id}/guardar-plantilla-retencion` ([doc API](../api/transacciones/compras))

---

## CU033: Emitir retención y descontar CxP

**Actores:** Asistente de Compras, Administrador.

**Descripción:** Registrar y emitir retención para disminuir pasivo pendiente con proveedor.

**Precondiciones:**

- Compra registrada.
- Retención digitada correctamente.

**Flujo de Eventos Básico:**

1. Registrar retención emitida de compra.
2. Emitir/enviar proceso FE de retención.
3. Sistema actualiza saldo de CxP según valor retenido.

**Flujos Alternativos:**

- Retención excede saldo pendiente: rechazo.

**Postcondiciones:**

- Retención emitida y CxP recalculada.

**APIs involucradas:**

- `POST /api/v1/compras/{compra_id}/retenciones` ([doc API](../api/transacciones/compras))
- `POST /api/v1/retenciones/{retencion_id}/emitir` ([doc API](../api/transacciones/compras))
- `GET /api/v1/retenciones/{retencion_id}/fe-payload` ([doc API](../api/transacciones/compras))

---

## CU034: Registrar pagos a proveedores (CxP)

**Actores:** Tesorería, Asistente de Compras, Administrador.

**Descripción:** Registrar pagos parciales o totales para saldar deudas de compras.

**Precondiciones:**

- CxP activa asociada a compra.
- Usuario con permisos de tesorería/compras.

**Flujo de Eventos Básico:**

1. El actor consulta bandeja CxP.
2. Selecciona compra y revisa saldo pendiente.
3. Registra pago indicando monto, fecha y forma de pago.
4. El sistema aplica bloqueo pesimista, valida sobrepago y recalcula estado.

**Flujos Alternativos:**

- Si el pago supera el saldo pendiente, el sistema rechaza con `400`.
- Si la CxP está anulada, el sistema rechaza el pago.

**Postcondiciones:**

- CxP actualizada en `PARCIAL` o `PAGADA`.
- Pago registrado en historial de pagos de proveedor.

**APIs involucradas:**

- `GET /api/v1/cxp` ([doc API](../api/transacciones/compras))
- `GET /api/v1/cxp/{compra_id}` ([doc API](../api/transacciones/compras))
- `POST /api/v1/cxp/{compra_id}/pagos` ([doc API](../api/transacciones/compras))
