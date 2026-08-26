---
id: checklist-integracion-frontend
title: "Ventas: Checklist de Integración Frontend"
sidebar_position: 1
---

# Ventas: Checklist de Integración Frontend

Este documento resume la auditoría técnica de frontend para el módulo de ventas y facturación (electrónica y nota de venta física), considerando reglas SRI y comportamiento real del backend.

## Cobertura de Endpoints (Estado Actual)

| Bloque | Endpoint | Estado |
|---|---|---|
| Venta | `POST /api/v1/ventas` | Implementado |
| Venta | `GET /api/v1/ventas` | Implementado |
| Venta | `POST /api/v1/ventas/desde-productos` | Implementado |
| Venta | `PUT /api/v1/ventas/{venta_id}` | Implementado |
| Venta | `PATCH /api/v1/ventas/{venta_id}` | Implementado |
| Venta | `GET /api/v1/ventas/{venta_id}` | Implementado |
| Venta | `POST /api/v1/ventas/{venta_id}/emitir` | Implementado |
| Venta | `POST /api/v1/ventas/{venta_id}/anular` | Implementado |
| Venta | `GET /api/v1/ventas/{venta_id}/fe-payload` | Implementado |
| Retenciones recibidas | `POST /api/v1/retenciones-recibidas` | Implementado |
| Retenciones recibidas | `GET /api/v1/retenciones-recibidas` | Implementado |
| Retenciones recibidas | `GET /api/v1/retenciones-recibidas/{retencion_id}` | Implementado |
| Retenciones recibidas | `POST /api/v1/retenciones-recibidas/{retencion_id}/aplicar` | Implementado |
| Retenciones recibidas | `POST /api/v1/retenciones-recibidas/{retencion_id}/anular` | Implementado |
| CxC | `GET /api/v1/cxc` | Implementado |
| CxC | `GET /api/v1/cxc/{venta_id}` | Implementado |
| CxC | `POST /api/v1/cxc/{venta_id}/pagos` | Implementado |
| FE cola | `POST /api/v1/fe/procesar-cola` | Implementado |
| FE cola | `GET /api/v1/fe/cola` | Implementado |
| FE cola | `POST /api/v1/fe/procesar/{documento_id}` | Implementado |
| FE cola | `POST /api/v1/fe/procesar-manual` | Implementado |
| Documentos FE | `GET /api/v1/documentos/{documento_id}/xml` | Implementado |
| Documentos FE | `GET /api/v1/documentos/{documento_id}/ride` | Implementado |
| Impresión | `GET /api/v1/impresion/documento/{documento_id}/a4` | Implementado |
| Impresión | `GET /api/v1/impresion/documento/{documento_id}/ticket` | Implementado |
| Impresión | `GET /api/v1/impresion/documento/{documento_id}/preimpresa` | Implementado |
| Impresión | `POST /api/v1/impresion/documento/{documento_id}/reimprimir` | Implementado |

## Ejemplos Rápidos para Front

### 1) Guardar y emitir venta en un solo paso (default)

`POST /api/v1/ventas`

```json
{
  "cliente_id": null,
  "empresa_id": "UUID_EMPRESA",
  "punto_emision_id": "UUID_PUNTO",
  "fecha_emision": "2026-02-25",
  "tipo_identificacion_comprador": "CEDULA",
  "identificacion_comprador": "0912345678",
  "forma_pago": "EFECTIVO",
  "tipo_emision": "ELECTRONICA",
  "regimen_emisor": "GENERAL",
  "usuario_auditoria": "frontend@demo",
  "detalles": [
    {
      "producto_id": "UUID_PRODUCTO",
      "descripcion": "Producto A",
      "cantidad": "1.0000",
      "precio_unitario": "10.00",
      "descuento": "0.00",
      "es_actividad_excluida": false,
      "impuestos": [
        {
          "tipo_impuesto": "IVA",
          "codigo_impuesto_sri": "2",
          "codigo_porcentaje_sri": "4",
          "tarifa": "15.00"
        }
      ]
    }
  ]
}
```

Resultado esperado: `201`, venta en `EMITIDA`, inventario egresado, CxC creada y documento FE en cola.

### 2) Listado comercial de ventas

`GET /api/v1/ventas?limit=20&offset=0&fecha_inicio=2026-02-01&fecha_fin=2026-02-28`

Campos clave por item: `fecha_emision`, `cliente`, `numero_factura`, `valor_total`, `estado`, `estado_sri`, `tipo_emision`.

### 3) Bandeja operativa de cola FE

`GET /api/v1/fe/cola?limit=50&offset=0&incluir_no_vencidos=true&tipo_documento=FACTURA`

Para envío manual:

- Un documento: `POST /api/v1/fe/procesar/{documento_id}`
- Varios/todos: `POST /api/v1/fe/procesar-manual`
- Reproceso por criterio de vencimiento: `POST /api/v1/fe/procesar-cola`

### 4) Listado general de CxC

`GET /api/v1/cxc?limit=20&offset=0&estado=PENDIENTE&texto=001-001`

Campos clave por item: `cliente`, `numero_factura`, `fecha_emision`, `valor_total_factura`, `saldo_pendiente`, `estado`.

## Checklist Frontend (Pantallas y Flujos)

### 1) Facturación de ventas

- Formulario de venta con detalle de ítems y validación decimal.
- Soporte de `tipo_emision`:
  - `ELECTRONICA`
  - `NOTA_VENTA_FISICA`
- Regla RIMPE Negocio Popular:
  - bloquea IVA > 0% salvo `es_actividad_excluida=true`.
- Manejo de estados:
  - venta (`BORRADOR`, `EMITIDA`, `ANULADA`)
  - SRI (`PENDIENTE`, `ENVIADO`, `AUTORIZADO`, `RECHAZADO`, `ERROR`)

### 2) Cobros y CxC

- Vista de cuenta por cobrar por venta.
- Registro de pagos múltiples por forma de pago SRI.
- Bloqueo de sobrepago con error funcional (`400`).
- Refresco de estado (`PENDIENTE`, `PARCIAL`, `PAGADA`, `ANULADA`).

### 3) Retenciones recibidas (a favor de la empresa)

- Registro en BORRADOR.
- Aplicación sobre CxC con lock de concurrencia.
- Anulación con motivo obligatorio y reverso del saldo de CxC.
- Validación de formato de número de retención `NNN-NNN-NNNNNNNNN`.

### 4) Facturación electrónica (SRI)

- Polling/control de estado del documento después de emisión.
- Worker automático de cola SRI configurable por entorno.
- Endpoint administrativo manual (`/api/v1/fe/procesar-cola`) como soporte operativo.
- Descarga de XML/RIDE solo para documentos AUTORIZADOS.

### 5) Impresión y reimpresión controlada

- RIDE A4 (PDF), ticket térmico (HTML), preimpresa (HTML/PDF).
- Reimpresión con motivo y formato.
- Manejo de permisos por rol en reimpresión (`CAJERO`, `ADMIN`, `ADMINISTRADOR`).

## Requisitos Técnicos para Levantar Front de Ventas

## Seguridad y headers

- Header principal: `Authorization: Bearer <token>`.
- Header auxiliar en desarrollo: `X-User-Id` (solo en entornos no productivos).
- `ENVIRONMENT` controla la aceptación de `X-User-Id`.

## Variables de entorno críticas (backend)

| Variable | Uso |
|---|---|
| `ENVIRONMENT` | Habilita/inhabilita `X-User-Id` en middleware de identidad |
| `SRI_MODO_EMISION` | Valida si el sistema opera en modo electrónico |
| `FEEC_AMBIENTE` | `pruebas` o `produccion` para generación FE |
| `FEEC_TIPO_EMISION` | Tipo de emisión FE (`1` normal, `2` contingencia) |
| `FEEC_REGIMEN` | Régimen tributario para FE-EC |
| `FEEC_P12_PATH` | Ruta certificado firma electrónica |
| `FEEC_P12_PASSWORD` | Password del certificado |
| `FEEC_XSD_PATH` | Ruta de XSD para validación XML |
| `DATABASE_URL` | Conexión principal DB |
| `FE_QUEUE_AUTO_PROCESS_ENABLED` | Habilita worker automático de cola FE |
| `FE_QUEUE_POLL_INTERVAL_SECONDS` | Intervalo en segundos del worker FE (>=5) |

## Dependencias y runtime relevantes

- `fe-ec` (orquestación FE y firma/envío SRI).
- `psycopg` + SQLAlchemy/SQLModel.
- WeasyPrint/Jinja2/python-barcode son opcionales en runtime:
  - si no están, existen fallbacks para no romper flujo MVP.

## Catálogos que el frontend debe cargar previamente

- Empresa (régimen, modo emisión, obligado contabilidad).
- Punto de emisión y secuenciales.
- Producto e impuestos (IVA/ICE).
- Bodega/stock para validación comercial.

## Hallazgos y Brechas Reales (Backend Actual)

Sin brechas críticas en endpoints para frontend de ventas/cobros del MVP.
