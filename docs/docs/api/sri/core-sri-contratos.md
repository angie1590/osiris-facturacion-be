---
id: core-sri-contratos
title: "SRI: Core Contracts (Enums y Reglas Tributarias)"
sidebar_position: 2
---

# SRI: Core Contracts (Enums y Reglas Tributarias)

Este documento describe los contratos transversales definidos en `src/osiris/modules/sri/core_sri` y usados por ventas, compras, FE y reportería.

## Enums transversales más usados

### Identificación y pagos

| Enum | Valores |
|---|---|
| `TipoIdentificacionSRI` | `RUC`, `CEDULA`, `PASAPORTE` |
| `FormaPagoSRI` | `EFECTIVO`, `TARJETA`, `TRANSFERENCIA` |

### Impuestos

| Enum | Valores |
|---|---|
| `TipoImpuestoMVP` | `IVA`, `ICE` |
| `TipoRetencionSRI` | `RENTA`, `IVA` |

### Estados de documentos/transacciones

| Enum | Valores |
|---|---|
| `EstadoVenta` | `BORRADOR`, `EMITIDA`, `ANULADA` |
| `EstadoCompra` | `BORRADOR`, `REGISTRADA`, `ANULADA` |
| `EstadoSriDocumento` | `PENDIENTE`, `ENVIADO`, `REINTENTO`, `AUTORIZADO`, `RECHAZADO`, `ERROR` |
| `EstadoDocumentoElectronico` | `EN_COLA`, `FIRMADO`, `RECIBIDO`, `ENVIADO`, `AUTORIZADO`, `RECHAZADO`, `DEVUELTO` |
| `EstadoColaSri` | `PENDIENTE`, `PROCESANDO`, `REINTENTO_PROGRAMADO`, `COMPLETADO`, `FALLIDO` |

## Reglas matemáticas base (`core_sri/schemas.py`)

## Redondeo

- Se usa redondeo contable a 2 decimales (`q2`) con `ROUND_HALF_UP`.

## Códigos IVA internos

| Grupo | Códigos |
|---|---|
| IVA 12% | `2` |
| IVA 15% | `4` |
| IVA 0% | `0` |
| No objeto | `6` |

## Reglas del detalle tributario (`VentaCompraDetalleCreate`)

1. Un detalle puede tener máximo:
   - 1 IVA
   - 1 ICE
2. Si `tipo_impuesto=IVA`, `codigo_impuesto_sri` debe ser `"2"`.
3. Si `tipo_impuesto=ICE`, `codigo_impuesto_sri` debe ser `"3"`.
4. Base imponible del IVA:
   - `base_iva = subtotal_sin_impuesto + monto_ice_detalle`
5. Cálculo de impuesto:
   - `valor_impuesto = base_imponible * tarifa / 100`

## Ejemplo de payload de detalle válido

```json
{
  "producto_id": "UUID_PRODUCTO",
  "descripcion": "Producto gravado",
  "cantidad": "2.0000",
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
```

## Errores de validación esperados

| Caso | Error esperado |
|---|---|
| Más de un IVA en el mismo detalle | `400` (ValueError de validación) |
| Más de un ICE en el mismo detalle | `400` |
| IVA con `codigo_impuesto_sri != "2"` | `400` |
| ICE con `codigo_impuesto_sri != "3"` | `400` |
| cantidad `<= 0` | `422`/`400` por esquema |

## Modelos `core_sri` sin endpoints directos

- `src/osiris/modules/sri/core_sri/router.py` es solo de organización de dominio.
- Los modelos y enums de `core_sri` son contratos internos usados por:
  - `ventas`
  - `compras`
  - `sri/facturacion_electronica`
  - `reportes`

## Catálogos auxiliares del dominio SRI

- `aux_tipo_contribuyente` (`src/osiris/modules/sri/tipo_contribuyente/entity.py`) existe como tabla de apoyo.
- Actualmente no tiene endpoint público en `api/v1`; se consume de forma indirecta desde módulos `common` (por ejemplo Empresa/Proveedor).
