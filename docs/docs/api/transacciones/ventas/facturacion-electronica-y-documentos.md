---
id: facturacion-electronica-y-documentos
title: "Ventas: Facturación Electrónica (SRI), Cola y Documentos"
sidebar_position: 3
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# Ventas: Facturación Electrónica (SRI), Cola y Documentos

## Alcance

Este documento cubre la orquestación de FE-EC para ventas:

1. Encolado y procesamiento asíncrono de documentos SRI.
2. Reintentos por errores de red y detención por rechazo lógico.
3. Descarga de XML autorizado y RIDE.

## Variables de entorno FE obligatorias

Cuando `SRI_MODO_EMISION=ELECTRONICO`, el backend exige:

| Variable | Requerida | Descripción |
|---|---|---|
| `FEEC_P12_PATH` | Sí | Ruta del certificado `.p12` |
| `FEEC_P12_PASSWORD` | Sí | Password del certificado |
| `FEEC_XSD_PATH` | Sí | Ruta de esquemas XSD |
| `FEEC_AMBIENTE` | Sí | `pruebas` o `produccion` |
| `FEEC_TIPO_EMISION` | Sí | `1` (normal), `2` (contingencia) |
| `FEEC_REGIMEN` | Sí | Régimen tributario de operación |
| `FE_QUEUE_AUTO_PROCESS_ENABLED` | No (default `true`) | Habilita worker automático de cola FE |
| `FE_QUEUE_POLL_INTERVAL_SECONDS` | No (default `60`) | Frecuencia del worker FE (mínimo 5) |

Si faltan, la app falla al startup (fail-fast).

## Estados FE (operativos)

| Entidad | Estado |
|---|---|
| Documento electrónico | `EN_COLA`, `FIRMADO`, `RECIBIDO`, `AUTORIZADO`, `RECHAZADO`, `DEVUELTO` |
| Venta estado_sri | `PENDIENTE`, `ENVIADO`, `AUTORIZADO`, `RECHAZADO`, `ERROR` |

## Flujo de procesamiento recomendado para frontend

1. Guardar venta (`POST /api/v1/ventas` o `/api/v1/ventas/desde-productos`).
2. Por defecto la venta queda emitida y encolada automáticamente para SRI.
3. Consultar cola FE (`GET /api/v1/fe/cola`) para monitoreo operativo.
4. Consultar venta (`GET /api/v1/ventas/{id}`) para estado comercial + `estado_sri`.
5. El worker interno procesa la cola automáticamente según `FE_QUEUE_POLL_INTERVAL_SECONDS`.
6. Opcional manual:
   - una factura: `POST /api/v1/fe/procesar/{documento_id}`
   - varias/todas: `POST /api/v1/fe/procesar-manual`
   - procesamiento vencido: `POST /api/v1/fe/procesar-cola`
7. Cuando el estado quede `AUTORIZADO`, habilitar descarga XML/RIDE e impresión.

---

`GET /api/v1/fe/cola`
Proposito: listar facturas/retenciones pendientes de procesamiento SRI para backoffice.

Query params:

| Param | Tipo | Descripción |
|---|---|---|
| `limit` | int | tamaño de página |
| `offset` | int | desplazamiento |
| `incluir_no_vencidos` | bool | incluye documentos aún no vencidos por `next_retry_at` |
| `tipo_documento` | enum | `FACTURA` (default) o `RETENCION` |

Response ejemplo:

```json
{
  "items": [
    {
      "id": "f4a4d8b4-9f8d-460b-8c12-3f3ae2b2f4a9",
      "tipo_documento": "FACTURA",
      "referencia_id": "b57f2c44-03c3-4e1d-9f2b-7e5832d0a2d7",
      "venta_id": "b57f2c44-03c3-4e1d-9f2b-7e5832d0a2d7",
      "clave_acceso": null,
      "estado_sri": "EN_COLA",
      "intentos": 1,
      "next_retry_at": "2026-02-25T15:20:00Z",
      "mensajes_sri": null,
      "creado_en": "2026-02-25T15:18:01Z"
    }
  ],
  "meta": {
    "total": 1,
    "limit": 50,
    "offset": 0,
    "next_offset": null,
    "prev_offset": null,
    "has_more": false,
    "page": 1,
    "page_count": 1
  }
}
```

---

`POST /api/v1/fe/procesar/{documento_id}`
Proposito: forzar el procesamiento manual de un documento específico.

Response ejemplo:

```json
{
  "procesados": 1,
  "ids_procesados": ["f4a4d8b4-9f8d-460b-8c12-3f3ae2b2f4a9"],
  "errores": []
}
```

---

`POST /api/v1/fe/procesar-manual`
Proposito: procesar varios documentos específicos o todos los pendientes.

Request ejemplo (varias):

```json
{
  "documento_ids": ["UUID1", "UUID2"]
}
```

Request ejemplo (todas las facturas):

```json
{
  "procesar_todos": true,
  "tipo_documento": "FACTURA",
  "incluir_no_vencidos": true
}
```

Response:

```json
{
  "procesados": 2,
  "ids_procesados": [
    "6a159af3-6b07-44c5-8cdd-9066427c5bb4",
    "f4a4d8b4-9f8d-460b-8c12-3f3ae2b2f4a9"
  ],
  "errores": []
}
```

---

`POST /api/v1/fe/procesar-cola`
Proposito: procesa manualmente documentos pendientes/reintento vencido en cola SRI.

<Tabs>
<TabItem value="response" label="Response 200">

```json
{
  "procesados": 3
}
```

</TabItem>
</Tabs>

Reglas:

- El worker automático ejecuta este mismo criterio de forma periódica.
- Solo procesa estados elegibles (`EN_COLA`, `RECIBIDO`), `intentos < 5` y `next_retry_at <= now`.
- Backoff de reintentos en minutos: 2, 4, 8, ...
- Rechazo lógico (`RECHAZADO/DEVUELTO`) detiene reintentos.

Ejemplo de ejecución manual para todas las facturas pendientes:

```bash
curl -X POST "http://localhost:8000/api/v1/fe/procesar-manual" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "procesar_todos": true,
    "tipo_documento": "FACTURA",
    "incluir_no_vencidos": true
  }'
```

---

`GET /api/v1/documentos/{documento_id}/xml`
Proposito: descarga XML autorizado.

Reglas:

- Requiere usuario autenticado y autorizado para la empresa dueña del documento.
- Solo si estado SRI del documento es `AUTORIZADO`.

Respuestas:

| HTTP | Caso |
|---|---|
| 200 | XML autorizado (`Content-Type: application/xml`) |
| 400 | Documento aún no autorizado |
| 403 | Usuario sin acceso |
| 404 | Documento o XML no disponible |

---

`GET /api/v1/documentos/{documento_id}/ride`
Proposito: entrega RIDE base (HTML) del documento autorizado.

Respuestas:

| HTTP | Caso |
|---|---|
| 200 | HTML RIDE |
| 400 | Documento no autorizado |
| 403 | Usuario sin acceso |
| 404 | Documento/venta/retención asociada no encontrada |

## Reglas SRI específicas implementadas

1. `codDoc` para factura electrónica: `"01"`.
2. Para RIMPE_NEGOCIO_POPULAR en electrónica:
   - inyección obligatoria en `infoAdicional`:
     - `Contribuyente Negocio Popular - Régimen RIMPE`
3. Validación de coherencia tributaria:
   - sumatoria de impuestos de detalle vs cabecera,
   - total con impuestos vs importe total.

## Errores y troubleshooting para frontend

| Escenario | Acción recomendada en frontend |
|---|---|
| Timeout/red SRI | Mostrar estado "Enviado/Reintento", no bloquear venta |
| RECHAZADO | Mostrar mensaje exacto de `sri_ultimo_error` |
| AUTORIZADO | Habilitar XML/RIDE e impresión |
| 403 en XML/RIDE | Verificar usuario/empresa asociada y token |

## Checklist operativo anti-sanciones SRI

1. No marcar factura como finalizada hasta `AUTORIZADO`.
2. Guardar y mostrar `clave_acceso` en UI.
3. Exponer mensaje de rechazo sin truncar.
4. Separar ambiente visual de pruebas/producción para evitar envíos equivocados.
5. Mantener trazabilidad de anulaciones con confirmación previa en portal SRI.
