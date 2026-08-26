---
id: impresion-documentos-y-reimpresion
title: "Impresión: Documentos, Formatos y Reimpresión"
sidebar_position: 2
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# Impresión: Documentos, Formatos y Reimpresión

## Alcance del módulo

Este módulo expone servicios de impresión para documentos electrónicos autorizados:

1. RIDE A4 (PDF)
2. Ticket térmico (58mm/80mm)
3. Plantilla preimpresa para nota física (HTML/PDF)
4. Reimpresión auditada

---

`GET /api/v1/impresion/documento/{documento_id}/a4`

Propósito: generar el RIDE en PDF A4.

Respuesta:

- `200` con `Content-Type: application/pdf`
- Header `Content-Disposition: inline; filename="ride-{documento_id}.pdf"`

Reglas:

- Documento debe existir y estar `AUTORIZADO`.
- Si no cumple: `400` o `404`.

---

`GET /api/v1/impresion/documento/{documento_id}/ticket`

Propósito: generar ticket térmico HTML.

Query params:

| Param | Tipo | Default | Valores |
|---|---|---|---|
| `ancho` | string | `80mm` | `58mm`, `80mm` |

Incluye:

- subtotal, IVA total, total
- total pagado
- efectivo y cambio
- clave de acceso

<Tabs>
<TabItem value="response-ticket" label="Response 200 (HTML)">

```html
<!doctype html>
<html>
  <body>
    <div>RAZON SOCIAL</div>
    <div>CLAVE: 012345...</div>
    <div>TOTAL: 25.00</div>
  </body>
</html>
```

</TabItem>
</Tabs>

---

`GET /api/v1/impresion/documento/{documento_id}/preimpresa`

Propósito: generar formato para nota de venta física preimpresa.

Query params:

| Param | Tipo | Default | Valores |
|---|---|---|---|
| `formato` | string | `HTML` | `HTML`, `PDF` |

Configuración usada desde `PuntoEmision.config_impresion`:

- `margen_superior_cm`
- `max_items_por_pagina`

Comportamiento:

- Si ítems exceden `max_items_por_pagina`, divide páginas lógicamente.
- Devuelve warning en header `X-Impresion-Warning`.

---

`POST /api/v1/impresion/documento/{documento_id}/reimprimir`

Propósito: reimpresión segura con auditoría.

<Tabs>
<TabItem value="request" label="Request">

```json
{
  "motivo": "Se atascó el papel",
  "formato": "A4"
}
```

</TabItem>
<TabItem value="request-formats" label="Formatos válidos">

```json
{
  "formato": "A4"
}
```

```json
{
  "formato": "TICKET_80MM"
}
```

```json
{
  "formato": "TICKET_58MM"
}
```

</TabItem>
</Tabs>

Reglas:

1. Valida autenticación y rol (`CAJERO|ADMIN|ADMINISTRADOR`).
2. `motivo` obligatorio.
3. Incrementa contadores de impresión.
4. Guarda evento `REIMPRESION_DOCUMENTO` en `AuditLog`.

Errores frecuentes:

| HTTP | Motivo |
|---|---|
| `400` | Formato inválido, documento no autorizado, motivo vacío |
| `403` | Usuario no autenticado o rol no permitido |
| `404` | Documento inexistente |

## Notas de integración frontend

1. Para ticket, abrir HTML en nueva ventana o contenedor de print.
2. Para A4/preimpresa PDF, consumir directamente el `blob` PDF.
3. Leer y mostrar `X-Impresion-Warning` en preimpresa cuando exista.
