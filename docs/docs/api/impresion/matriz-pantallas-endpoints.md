---
id: matriz-pantallas-endpoints
title: "Impresión: Matriz Pantallas ↔ Endpoints"
sidebar_position: 2
---

# Impresión: Matriz Pantallas ↔ Endpoints

Matriz operativa para implementación frontend del módulo de impresión.

## Matriz principal

| Pantalla/Acción Front | Método + Endpoint | Query/Path | Payload mínimo | Success | Errores esperados |
|---|---|---|---|---|---|
| Ver factura en A4 | `GET /api/v1/impresion/documento/{documento_id}/a4` | `documento_id` | N/A | `200` + `application/pdf` | `400` no autorizado, `404` no existe |
| Imprimir ticket térmico | `GET /api/v1/impresion/documento/{documento_id}/ticket` | `documento_id`, `ancho=58mm\|80mm` | N/A | `200` + `text/html` | `400` ancho inválido o documento no autorizado, `404` |
| Imprimir nota preimpresa (HTML) | `GET /api/v1/impresion/documento/{documento_id}/preimpresa` | `documento_id`, `formato=HTML` | N/A | `200` + `text/html` | `400`, `404` |
| Imprimir nota preimpresa (PDF) | `GET /api/v1/impresion/documento/{documento_id}/preimpresa` | `documento_id`, `formato=PDF` | N/A | `200` + `application/pdf` | `400`, `404` |
| Reimprimir A4 | `POST /api/v1/impresion/documento/{documento_id}/reimprimir` | `documento_id` | `{ "motivo": "...", "formato": "A4" }` | `200` + `application/pdf` | `400` motivo/formato/doc inválido, `403` rol, `404` |
| Reimprimir ticket 80mm | `POST /api/v1/impresion/documento/{documento_id}/reimprimir` | `documento_id` | `{ "motivo": "...", "formato": "TICKET_80MM" }` | `200` + `text/html` | `400`, `403`, `404` |
| Reimprimir ticket 58mm | `POST /api/v1/impresion/documento/{documento_id}/reimprimir` | `documento_id` | `{ "motivo": "...", "formato": "TICKET_58MM" }` | `200` + `text/html` | `400`, `403`, `404` |

## Payload mínimo para reimpresión

```json
{
  "motivo": "Se atascó el papel",
  "formato": "A4"
}
```

## Reglas UI críticas

1. No mostrar botones de impresión si estado del documento no es `AUTORIZADO`.
2. En preimpresa, leer header `X-Impresion-Warning` y mostrar aviso al usuario.
3. En reimpresión, abrir modal de motivo obligatorio antes de enviar.
4. Manejar descarga/render según `Content-Type`:
   - `application/pdf`: abrir blob PDF
   - `text/html`: abrir vista imprimible
