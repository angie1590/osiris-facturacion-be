---
id: checklist-integracion-frontend
title: "Impresión: Checklist de Integración Frontend"
sidebar_position: 1
---

# Impresión: Checklist de Integración Frontend

Este documento cubre el módulo `src/osiris/modules/impresion` y su contrato real de endpoints.

## Cobertura de Endpoints (estado actual)

| Endpoint | Propósito | Formato |
|---|---|---|
| `GET /api/v1/impresion/documento/{documento_id}/a4` | Generar RIDE A4 | PDF (`application/pdf`) |
| `GET /api/v1/impresion/documento/{documento_id}/ticket` | Generar ticket térmico | HTML (`text/html`) |
| `GET /api/v1/impresion/documento/{documento_id}/preimpresa` | Formato para nota física preimpresa | HTML/PDF |
| `POST /api/v1/impresion/documento/{documento_id}/reimprimir` | Reimpresión controlada con auditoría | PDF/HTML según formato |

## Reglas de negocio relevantes

1. Solo se imprime/reimprime documentos con estado SRI `AUTORIZADO`.
2. Reimpresión exige rol:
   - `CAJERO`
   - `ADMIN`
   - `ADMINISTRADOR`
3. Cada reimpresión:
   - incrementa `cantidad_impresiones` en `DocumentoElectronico`
   - incrementa `cantidad_impresiones` en `Venta` (si aplica)
   - registra `REIMPRESION_DOCUMENTO` en `AuditLog`
4. Para preimpresa, si el número de ítems excede la configuración de página, la API devuelve warning en `X-Impresion-Warning`.

## Dependencias y fallback de runtime

- Plantillas: Jinja2.
- PDF: WeasyPrint (con fallback de render cuando no está disponible).
- Código de barras: `python-barcode` (con fallback SVG textual si no está instalado).

## Header y errores esperados

| HTTP | Caso |
|---|---|
| `200` | Generación correcta |
| `400` | Documento no autorizado o parámetros inválidos |
| `403` | Sin permiso para reimpresión |
| `404` | Documento o venta asociada no encontrada |

## Checklist UI mínimo

- Vista documento autorizado con acciones:
  - imprimir A4
  - imprimir ticket (58mm/80mm)
  - imprimir preimpresa
- Modal de reimpresión con:
  - motivo obligatorio
  - selección de formato (`A4`, `TICKET_80MM`, `TICKET_58MM`)
- Manejo de warning para preimpresa:
  - leer y mostrar `X-Impresion-Warning` si viene en header.

## Referencia de implementación por pantalla

Para una guía directa de construcción de UI por flujo:

- `API > Impresión > Impresión: Matriz Pantallas ↔ Endpoints`
