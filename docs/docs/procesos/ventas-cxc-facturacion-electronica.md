---
id: procesos-ventas-cxc-facturacion-electronica
title: "05. Ventas, CxC y Facturación Electrónica"
sidebar_position: 6
---

# 05. Ventas, CxC y Facturación Electrónica

## CU040: Registrar y emitir venta automáticamente

**Actores:** Asistente de Ventas, Cajero.

**Descripción:** Al guardar venta, disparar en una sola operación: validación tributaria, egreso de inventario, creación de CxC y encolado FE cuando aplica.

**Precondiciones:**

- Cliente y productos disponibles.
- Stock suficiente por bodega.
- Empresa activa en sesión.

**Flujo de Eventos Básico:**

1. El actor registra cabecera y detalle de venta.
2. El frontend envía `emitir_automaticamente=true` (default).
3. El sistema valida reglas RIMPE/IVA y cálculos.
4. El sistema descuenta inventario.
5. El sistema crea CxC pendiente.
6. Si es electrónica, encola documento FE.
7. Retorna venta emitida.

**Flujos Alternativos:**

- Stock insuficiente: rechazo y rollback total.
- Regla tributaria RIMPE incumplida: rechazo.

**Postcondiciones:**

- Venta `EMITIDA`, inventario actualizado, CxC creada y FE en cola (si aplica).

**APIs involucradas:**

- `POST /api/v1/ventas` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))
- `POST /api/v1/ventas/desde-productos` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))

---

## CU041: Emitir venta manual desde borrador

**Actores:** Asistente de Ventas, Supervisor.

**Descripción:** Permitir guardar borrador y emitir en un paso posterior controlado.

**Precondiciones:**

- Venta en estado `BORRADOR`.

**Flujo de Eventos Básico:**

1. Crear venta con `emitir_automaticamente=false`.
2. Revisar documento.
3. Ejecutar emisión manual.

**Flujos Alternativos:**

- Venta ya emitida/anulada: rechazo.

**Postcondiciones:**

- Venta pasa a `EMITIDA` y ejecuta el mismo pipeline operativo.

**APIs involucradas:**

- `POST /api/v1/ventas?emitir_automaticamente=false` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))
- `POST /api/v1/ventas/{venta_id}/emitir` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))

---

## CU042: Anular venta con reverso y control SRI

**Actores:** Administrador, Supervisor de Ventas.

**Descripción:** Anular venta aplicando reglas por tipo de emisión y reversando impactos operativos.

**Precondiciones:**

- Venta emitida.
- Si FE autorizada, confirmación previa de gestión en portal SRI.

**Flujo de Eventos Básico:**

1. El actor envía solicitud de anulación con motivo.
2. El sistema valida pagos/retenciones y reglas FE.
3. Cambia estado de venta a `ANULADA`.
4. Reversa inventario y actualiza estado administrativo asociado.

**Flujos Alternativos:**

- Si hay cobros ya registrados, el sistema rechaza anulación.
- Si FE autorizada sin confirmación portal SRI, el sistema rechaza.

**Postcondiciones:**

- Venta anulada con trazabilidad completa.

**APIs involucradas:**

- `POST /api/v1/ventas/{venta_id}/anular` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))

---

## CU043: Gestionar cobranza de CxC

**Actores:** Cajero, Asistente de Cobranza.

**Descripción:** Registrar pagos parciales/totales y controlar sobrepago.

**Precondiciones:**

- Venta con CxC activa.

**Flujo de Eventos Básico:**

1. Consultar CxC por venta o listado general.
2. Registrar pago con forma de pago SRI.
3. Sistema recalcula saldo y estado (`PENDIENTE`, `PARCIAL`, `PAGADA`).

**Flujos Alternativos:**

- Pago mayor al saldo: rechazo.

**Postcondiciones:**

- CxC actualizada con saldo y estado correctos.

**APIs involucradas:**

- `GET /api/v1/cxc/{venta_id}` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))
- `GET /api/v1/cxc` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))
- `POST /api/v1/cxc/{venta_id}/pagos` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))

---

## CU044: Aplicar retenciones recibidas a CxC

**Actores:** Asistente de Cobranza, Administrador.

**Descripción:** Registrar retención recibida de cliente y aplicarla como abono en papel a cartera.

**Precondiciones:**

- Venta con CxC activa.
- Datos de comprobante de retención válidos.

**Flujo de Eventos Básico:**

1. Registrar retención recibida.
2. Aplicar retención sobre CxC.
3. Sistema reduce saldo y actualiza estado de la cuenta.
4. Si fue digitada erróneamente, se puede anular con motivo obligatorio.

**Flujos Alternativos:**

- Retención excede saldo pendiente: rechazo.
- Anulación sin motivo: rechazo.

**Postcondiciones:**

- CxC consistente con pagos + retenciones aplicadas.

**APIs involucradas:**

- `POST /api/v1/retenciones-recibidas` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))
- `POST /api/v1/retenciones-recibidas/{retencion_id}/aplicar` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))
- `POST /api/v1/retenciones-recibidas/{retencion_id}/anular` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))
- `GET /api/v1/retenciones-recibidas` ([doc API](../api/transacciones/ventas/ventas-ciclo-comercial))

---

## CU045: Operar cola FE (automática y manual)

**Actores:** Administrador, Supervisor de Facturación.

**Descripción:** Controlar envío/autorización SRI con worker automático y opciones manuales para casos urgentes.

**Precondiciones:**

- Documento FE en estado pendiente (`EN_COLA`/`RECIBIDO`).

**Flujo de Eventos Básico:**

1. Worker automático procesa cola periódicamente.
2. Usuario admin puede listar cola FE.
3. Usuario admin puede procesar 1, varios o todos manualmente.
4. Verificar resultado por estado FE del documento.

**Flujos Alternativos:**

- Timeout/red: se reintenta según política de contingencia.
- Rechazo SRI lógico: queda rechazado sin reintento automático.

**Postcondiciones:**

- Documentos FE actualizados y monitoreables.

**APIs involucradas:**

- `GET /api/v1/fe/cola` ([doc API](../api/sri/facturacion-electronica-cola-documentos))
- `POST /api/v1/fe/procesar-cola` ([doc API](../api/sri/facturacion-electronica-cola-documentos))
- `POST /api/v1/fe/procesar/{documento_id}` ([doc API](../api/sri/facturacion-electronica-cola-documentos))
- `POST /api/v1/fe/procesar-manual` ([doc API](../api/sri/facturacion-electronica-cola-documentos))

---

## CU046: Descargar XML y RIDE del documento electrónico

**Actores:** Asistente de Ventas, Administración.

**Descripción:** Obtener comprobante autorizado para cliente o control interno.

**Precondiciones:**

- Documento FE existente.
- Usuario autorizado sobre la empresa del documento.

**Flujo de Eventos Básico:**

1. Solicitar XML autorizado.
2. Solicitar RIDE para visualización/descarga.

**Flujos Alternativos:**

- Documento no autorizado/no accesible: rechazo.

**Postcondiciones:**

- Documento descargado para soporte operativo/comercial.

**APIs involucradas:**

- `GET /api/v1/documentos/{documento_id}/xml` ([doc API](../api/sri/facturacion-electronica-cola-documentos))
- `GET /api/v1/documentos/{documento_id}/ride` ([doc API](../api/sri/facturacion-electronica-cola-documentos))

