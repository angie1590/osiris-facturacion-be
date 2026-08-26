---
id: checklist-integracion-frontend
title: "SRI: Checklist de Integración Frontend"
sidebar_position: 1
---

# SRI: Checklist de Integración Frontend

Este documento resume lo que el frontend necesita para integrar correctamente el módulo `src/osiris/modules/sri`, sin romper reglas tributarias ni operativas del SRI.

## Cobertura de Endpoints (Estado actual)

| Bloque | Endpoint | Estado |
|---|---|---|
| Catálogo impuestos | `GET /api/v1/impuestos` | Implementado |
| Catálogo impuestos | `GET /api/v1/impuestos/activos-vigentes` | Implementado |
| Catálogo impuestos | `GET /api/v1/impuestos/{impuesto_id}` | Implementado |
| Catálogo impuestos | `POST /api/v1/impuestos` | Implementado |
| Catálogo impuestos | `PUT /api/v1/impuestos/{impuesto_id}` | Implementado |
| Catálogo impuestos | `DELETE /api/v1/impuestos/{impuesto_id}` | Implementado |
| Cola FE | `POST /api/v1/fe/procesar-cola` | Implementado |
| Cola FE | `GET /api/v1/fe/cola` | Implementado |
| Cola FE | `POST /api/v1/fe/procesar/{documento_id}` | Implementado |
| Cola FE | `POST /api/v1/fe/procesar-manual` | Implementado |
| Documentos FE | `GET /api/v1/documentos/{documento_id}/xml` | Implementado |
| Documentos FE | `GET /api/v1/documentos/{documento_id}/ride` | Implementado |

## Nota de arquitectura importante

- `src/osiris/modules/sri/router.py` y `src/osiris/modules/sri/core_sri/router.py` **no exponen endpoints directos**.
- Los endpoints productivos del módulo `sri` están en:
  - `impuesto_catalogo/router.py`
  - `facturacion_electronica/router.py`

## Requisitos técnicos para frontend

1. Consumir montos/porcentajes como decimal en string (`"12.50"`), no `float`.
2. Tratar `DELETE /api/v1/impuestos/{id}` como borrado lógico (se marca `activo=false`).
3. Mostrar estados FE por documento (`EN_COLA`, `RECIBIDO`, `AUTORIZADO`, `RECHAZADO`, etc.).
4. Habilitar acciones manuales de cola FE para roles operativos (soporte/backoffice).
5. Para descarga XML/RIDE, manejar explícitamente:
   - `400`: documento aún no autorizado
   - `403`: usuario sin acceso
   - `404`: documento no existe o XML no disponible

## Variables de entorno críticas (backend SRI)

| Variable | Requerida | Uso |
|---|---|---|
| `SRI_MODO_EMISION` | Sí | `ELECTRONICO` o `NO_ELECTRONICO` |
| `FEEC_P12_PATH` | Condicional | Obligatoria si `SRI_MODO_EMISION=ELECTRONICO` |
| `FEEC_P12_PASSWORD` | Condicional | Password del certificado `.p12` |
| `FEEC_XSD_PATH` | Condicional | Ruta XSD para validación XML |
| `FEEC_AMBIENTE` | Sí | `pruebas` o `produccion` |
| `FEEC_TIPO_EMISION` | Sí | `1` normal, `2` contingencia |
| `FEEC_REGIMEN` | Sí | Régimen tributario FE |
| `FE_QUEUE_AUTO_PROCESS_ENABLED` | No | Habilita worker automático de cola |
| `FE_QUEUE_POLL_INTERVAL_SECONDS` | No | Intervalo del worker (mínimo 5) |

## Checklist funcional de front (mínimo MVP)

- Pantalla de catálogo de impuestos con filtros por `tipo_impuesto` y vigencia.
- Pantalla de monitoreo FE con acciones:
  - procesar uno
  - procesar selección
  - procesar todos
- Vista de documento FE con descarga de XML y RIDE.
- Manejo de errores contextuales según código HTTP y estado FE.
