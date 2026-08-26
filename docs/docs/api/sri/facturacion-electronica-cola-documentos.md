---
id: facturacion-electronica-cola-documentos
title: "SRI: Facturación Electrónica (Cola FE y Documentos)"
sidebar_position: 4
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# SRI: Facturación Electrónica (Cola FE y Documentos)

Este documento cubre `src/osiris/modules/sri/facturacion_electronica`.

## Alcance

1. Gestión de cola FE para facturas/retenciones.
2. Reintentos con backoff para errores de red.
3. Consulta/descarga de XML y RIDE.

## Estados operativos

### Documento electrónico (`DocumentoElectronico`)

`EN_COLA`, `FIRMADO`, `RECIBIDO`, `AUTORIZADO`, `RECHAZADO`, `DEVUELTO`

### Cola de envío (`DocumentoSriCola`)

`PENDIENTE`, `PROCESANDO`, `REINTENTO_PROGRAMADO`, `COMPLETADO`, `FALLIDO`

## Regla de reintentos

- Backoff exponencial en minutos para `DocumentoElectronico`: `2, 4, 8, ...` (`intentos < 5`).
- Rechazo lógico (`RECHAZADO`/`DEVUELTO`) detiene reintentos.
- Para errores de red/timeout, se programa próximo intento.

## Worker automático y operación manual

- El backend puede procesar automáticamente la cola según:
  - `FE_QUEUE_AUTO_PROCESS_ENABLED`
  - `FE_QUEUE_POLL_INTERVAL_SECONDS`
- Además hay endpoints manuales para soporte.

---

`POST /api/v1/fe/procesar-cola`

Propósito: procesa documentos pendientes que cumplen criterio de reintento vencido.

<Tabs>
<TabItem value="response" label="Response 200">

```json
{
  "procesados": 3
}
```

</TabItem>
</Tabs>

---

`GET /api/v1/fe/cola`

Propósito: listar documentos FE pendientes.

Query params:

| Param | Tipo | Descripción |
|---|---|---|
| `limit` | int | tamaño de página |
| `offset` | int | desplazamiento |
| `incluir_no_vencidos` | bool | incluye no vencidos por `next_retry_at` |
| `tipo_documento` | enum | `FACTURA` o `RETENCION` |

<Tabs>
<TabItem value="response-list" label="Response 200">

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

</TabItem>
</Tabs>

---

`POST /api/v1/fe/procesar/{documento_id}`

Propósito: forzar procesamiento manual de un documento específico.

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

Propósito: procesar varios IDs o todos los pendientes.

<Tabs>
<TabItem value="request-ids" label="Request por IDs">

```json
{
  "documento_ids": [
    "6a159af3-6b07-44c5-8cdd-9066427c5bb4",
    "f4a4d8b4-9f8d-460b-8c12-3f3ae2b2f4a9"
  ]
}
```

</TabItem>
<TabItem value="request-all" label="Request procesar todos">

```json
{
  "procesar_todos": true,
  "tipo_documento": "FACTURA",
  "incluir_no_vencidos": true
}
```

</TabItem>
<TabItem value="response-manual" label="Response 200">

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

</TabItem>
</Tabs>

---

`GET /api/v1/documentos/{documento_id}/xml`

Propósito: descargar XML autorizado.

Respuestas:

| HTTP | Caso |
|---|---|
| 200 | XML autorizado (`application/xml`) |
| 400 | documento no autorizado aún |
| 403 | usuario sin acceso al documento |
| 404 | documento o XML no disponible |

---

`GET /api/v1/documentos/{documento_id}/ride`

Propósito: devolver RIDE en HTML para visualización/descarga.

Respuestas:

| HTTP | Caso |
|---|---|
| 200 | HTML RIDE |
| 400 | documento no autorizado o tipo no soportado |
| 403 | usuario sin acceso |
| 404 | documento o entidad asociada no encontrada |

## Regla de seguridad de documentos

- Para XML/RIDE se valida que el usuario autenticado pertenezca a la empresa dueña del documento.
- Si no cumple, retorna `403`.

## Integración FE-EC en backend

- Si la librería FE-EC local no está disponible, hay fallback de ejecución mock para entornos de prueba.
- En producción, se usa:
  - firma XML (`ManejadorXML`)
  - envío recepción/autorización (`SRIService`)
- Se registra historial de cambios de estado en `DocumentoElectronicoHistorial`.

