---
id: cobertura-total-endpoints
title: "Cobertura Total de Endpoints (Backend -> Frontend)"
sidebar_position: 1
---

# Cobertura Total de Endpoints (Backend -> Frontend)

Este documento audita la cobertura de `docs/docs/api` contra los endpoints reales definidos en `src/osiris/modules/**/router.py`.

## Resultado de Auditoria

- Endpoints detectados en backend: `176`
- Endpoints documentados en `docs/docs/api`: `176`
- Cobertura: `100%`
- Routers agregadores sin endpoints directos (esperado por arquitectura):
  - `src/osiris/modules/common/router.py`
  - `src/osiris/modules/common/template/router.py`
  - `src/osiris/modules/inventario/router.py`
  - `src/osiris/modules/sri/router.py`
  - `src/osiris/modules/sri/core_sri/router.py`

## Matriz de Cobertura por Modulo

| Modulo backend | Endpoints | Documentacion frontend (fuente canonica) |
|---|---:|---|
| `common` | 72 | [Onboarding](./common/onboarding), [Seguridad y Accesos](./common/seguridad-accesos), [Empresa seleccionada por sesión](./common/empresa-seleccionada-sesion), [Directorio](./common/directorio) |
| `inventario` | 45 | [Checklist](./inventario/checklist-integracion-frontend), [Bloques](./inventario/bloques-construccion), [Casa comercial y bodega](./inventario/casa-comercial-bodega), [Producto + atributos/impuestos/bodegas](./inventario/producto-atributos-impuestos-bodegas), [Producto CRUD](./inventario/producto-crud-base) |
| `compras` | 12 | [Compras](./transacciones/compras) |
| `ventas` | 17 | [Checklist](./transacciones/ventas/checklist-integracion-frontend), [Ciclo comercial](./transacciones/ventas/ventas-ciclo-comercial), [FE y documentos](./transacciones/ventas/facturacion-electronica-y-documentos) |
| `sri` | 12 | [Checklist](./sri/checklist-integracion-frontend), [Core SRI](./sri/core-sri-contratos), [Catalogo impuestos](./sri/catalogo-impuestos), [FE cola/documentos](./sri/facturacion-electronica-cola-documentos) |
| `impresion` | 4 | [Checklist](./impresion/checklist-integracion-frontend), [Matriz pantallas/endpoints](./impresion/matriz-pantallas-endpoints), [Impresion y reimpresion](./impresion/impresion-documentos-y-reimpresion) |
| `reportes` | 14 | [Checklist](./reportes/checklist-integracion-frontend), [Matriz pantallas/endpoints](./reportes/matriz-pantallas-endpoints), [Ventas y rentabilidad](./reportes/ventas-y-rentabilidad), [Operativos y tributarios](./reportes/operativos-tributarios) |

## Cobertura de Endpoints Especiales (Criticos para Frontend)

### Common

- `POST /api/v1/puntos-emision/{punto_emision_id}/secuenciales/{tipo_documento}/siguiente`
- `POST /api/v1/puntos-emision/{punto_emision_id}/secuenciales/{tipo_documento}/ajuste-manual`
- `GET /api/v1/usuarios/{usuario_id}/permisos`
- `GET /api/v1/usuarios/{usuario_id}/menu`
- `POST /api/v1/usuarios/{usuario_id}/reset-password`
- `POST /api/v1/usuarios/{usuario_id}/verify-password`
- `GET /api/v1/audit-logs`

### Inventario

- `POST /api/v1/inventarios/movimientos`
- `POST /api/v1/inventarios/movimientos/{movimiento_id}/confirmar`
- `POST /api/v1/inventarios/movimientos/{movimiento_id}/anular`
- `POST /api/v1/inventarios/transferencias`
- `GET /api/v1/inventarios/kardex`
- `GET /api/v1/inventarios/valoracion`
- `GET /api/v1/inventarios/stock-disponible`

### Compras / Ventas / SRI / Impresion

- Compras:
  - `GET /api/v1/cxp`
  - `GET /api/v1/cxp/{compra_id}`
  - `POST /api/v1/cxp/{compra_id}/pagos`
  - `POST /api/v1/compras/{compra_id}/retenciones`
  - `POST /api/v1/retenciones/{retencion_id}/emitir`
  - `GET /api/v1/retenciones/{retencion_id}/fe-payload`
- Ventas:
  - `POST /api/v1/ventas/{venta_id}/emitir`
  - `POST /api/v1/ventas/{venta_id}/anular`
  - `GET /api/v1/cxc`
  - `POST /api/v1/cxc/{venta_id}/pagos`
- SRI FE:
  - `GET /api/v1/fe/cola`
  - `POST /api/v1/fe/procesar/{documento_id}`
  - `POST /api/v1/fe/procesar-manual`
  - `GET /api/v1/documentos/{documento_id}/xml`
  - `GET /api/v1/documentos/{documento_id}/ride`
- Impresion:
  - `GET /api/v1/impresion/documento/{documento_id}/a4`
  - `GET /api/v1/impresion/documento/{documento_id}/ticket`
  - `GET /api/v1/impresion/documento/{documento_id}/preimpresa`
  - `POST /api/v1/impresion/documento/{documento_id}/reimprimir`

## Convenciones que el Frontend Debe Respetar

1. Soft delete: por defecto se listan registros activos (`only_active=true` cuando aplique).
2. Paginacion: usar `limit` y `offset` en listados paginados.
3. Montos y porcentajes: enviar/consumir como decimal en string (no `float`).
4. FE-SRI: separar estado comercial del documento (`BORRADOR/EMITIDA/ANULADA`) de estado FE (`EN_COLA/RECIBIDO/AUTORIZADO/RECHAZADO`).
5. Reimpresion: siempre exigir motivo y usar formato permitido.
6. Multiempresa por sesion: usar contexto de empresa en JWT (`empresa_id`) para aislar operaciones y listados.

## Estado Final

- La documentacion actual cubre el contrato operativo para que frontend implemente flujos completos de:
  - Maestro común
  - Inventario
  - Compras
  - Ventas + CxC + retenciones recibidas
  - FE-SRI
  - Impresion
  - Reporteria
