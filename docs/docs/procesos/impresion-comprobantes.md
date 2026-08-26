---
id: procesos-impresion-comprobantes
title: "06. Impresión de Comprobantes"
sidebar_position: 7
---

# 06. Impresión de Comprobantes

## CU050: Generar RIDE A4 para documento electrónico

**Actores:** Asistente de Ventas, Administración.

**Descripción:** Generar representación imprimible A4 para facturas/retenciones electrónicas.

**Precondiciones:**

- Documento electrónico existente y accesible.

**Flujo de Eventos Básico:**

1. El actor solicita impresión A4 de documento.
2. El sistema genera contenido y responde PDF.

**Flujos Alternativos:**

- Documento no autorizado o fuera de alcance de empresa: rechazo.

**Postcondiciones:**

- PDF A4 disponible para impresión o envío.

**APIs involucradas:**

- `GET /api/v1/impresion/documento/{documento_id}/a4` ([doc API](../api/impresion/impresion-documentos-y-reimpresion))

---

## CU051: Generar ticket térmico POS

**Actores:** Cajero, Asistente de Ventas.

**Descripción:** Emitir ticket optimizado para impresoras térmicas (58mm/80mm).

**Precondiciones:**

- Documento o venta disponible para impresión.

**Flujo de Eventos Básico:**

1. El actor solicita ticket indicando ancho.
2. El sistema responde HTML/PDF térmico renderizado.
3. Front ejecuta impresión local en navegador/POS.

**Flujos Alternativos:**

- Formato no soportado: rechazo.

**Postcondiciones:**

- Ticket impreso en punto de venta.

**APIs involucradas:**

- `GET /api/v1/impresion/documento/{documento_id}/ticket?ancho=80mm` ([doc API](../api/impresion/impresion-documentos-y-reimpresion))

---

## CU052: Imprimir nota preimpresa (matricial)

**Actores:** Cajero, Supervisor de Caja.

**Descripción:** Imprimir detalle de nota de venta física sobre formato preimpreso.

**Precondiciones:**

- Punto de emisión con configuración de impresión preimpresa.
- Documento/venta física habilitada.

**Flujo de Eventos Básico:**

1. El actor solicita plantilla preimpresa.
2. El sistema aplica margen superior y límites de ítems.
3. Front imprime sobre formulario físico.

**Flujos Alternativos:**

- Cantidad de ítems supera capacidad por página: sistema advierte/segmenta según configuración.

**Postcondiciones:**

- Nota física emitida en formato correcto.

**APIs involucradas:**

- `GET /api/v1/impresion/documento/{documento_id}/preimpresa` ([doc API](../api/impresion/impresion-documentos-y-reimpresion))

---

## CU053: Reimpresión controlada con auditoría

**Actores:** Cajero autorizado, Administrador.

**Descripción:** Ejecutar reimpresiones con motivo obligatorio y traza auditable.

**Precondiciones:**

- Usuario con rol permitido.
- Motivo de reimpresión informado.

**Flujo de Eventos Básico:**

1. El actor solicita reimpresión indicando formato y motivo.
2. El sistema incrementa contador de impresiones.
3. El sistema registra evento de auditoría.
4. Retorna documento en formato solicitado.

**Flujos Alternativos:**

- Usuario sin permisos: operación denegada.
- Motivo vacío: rechazo.

**Postcondiciones:**

- Reimpresión ejecutada con trazabilidad completa.

**APIs involucradas:**

- `POST /api/v1/impresion/documento/{documento_id}/reimprimir` ([doc API](../api/impresion/impresion-documentos-y-reimpresion))
- `GET /api/v1/audit-logs` ([doc API](../api/common/seguridad-accesos))

