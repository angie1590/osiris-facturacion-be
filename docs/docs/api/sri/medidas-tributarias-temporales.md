---
id: medidas-tributarias-temporales
title: Medidas tributarias temporales
sidebar_position: 4
---

# Medidas tributarias temporales

Permite configurar excepciones de IVA/ICE por empresa, periodo y productos específicos. Las medidas no modifican `aux_impuesto_catalogo` ni los impuestos habituales asignados al producto.

## Administración y operación

- La API requiere token de acceso y rol `admin`/`administrador`; además valida el ámbito de empresa seleccionado.
- Toda medida nace `BORRADOR`. Una persona administradora registra referencia legal, fechas inclusivas, impuesto/componente, tarifa, código de porcentaje y productos alcanzados.
- La casilla de confirmación del código SRI es obligatoria para activar. Debe marcarse solo tras verificar la publicación oficial para el periodo y el ambiente de emisión.
- El IVA es porcentual. ICE puede ser `AD_VALOREM` o `ESPECIFICO`; el segundo exige para cada producto un factor positivo de unidad vendida a unidad gravable.
- Para “litro de alcohol puro” el factor debe calcularse para la unidad comercial del SKU, por ejemplo `litros_por_envase × graduación_alcohólica`. Osiris no infiere capacidad ni graduación desde la descripción del producto.
- No puede haber medidas activas solapadas para la misma empresa, producto, impuesto/componente y fechas.
- Una medida expirada no afecta ventas de fechas posteriores. Se evalúa `fecha_emision`, con fechas inicial/final inclusivas.
- La API no importa decretos ni confirma automáticamente códigos. Los valores de los decretos de ejemplo no se precargan porque las imágenes no acreditan el código de porcentaje que el SRI exige.

## Endpoints

| Método | Ruta | Función |
|---|---|---|
| GET | `/api/v1/medidas-tributarias-temporales` | Lista paginada, filtrable por empresa dentro del ámbito activo |
| GET | `/api/v1/medidas-tributarias-temporales/{id}` | Consulta una medida |
| POST | `/api/v1/medidas-tributarias-temporales` | Crea borrador |
| PUT | `/api/v1/medidas-tributarias-temporales/{id}` | Edita borrador/inactiva; una activa debe desactivarse primero |
| PATCH | `/api/v1/medidas-tributarias-temporales/{id}/estado` | Activa o desactiva |

## Ejemplo de borrador IVA

```json
{
  "empresa_id": "UUID_EMPRESA",
  "nombre": "Reducción temporal IVA servicios turísticos",
  "referencia_legal": "Decreto Ejecutivo, número y publicación oficial",
  "tipo_impuesto": "IVA",
  "componente": "PORCENTUAL",
  "fecha_inicio": "2026-10-09",
  "fecha_fin": "2026-10-11",
  "codigo_impuesto_sri": "2",
  "codigo_porcentaje_sri": "CODIGO_CONFIRMADO_SRI",
  "codigo_sri_confirmado": false,
  "tarifa": "8.00",
  "productos": [
    { "producto_id": "UUID_PRODUCTO_SERVICIO", "factor_cantidad": null, "unidad_gravable": null }
  ]
}
```

Reemplaza el código por el valor que el SRI confirme; `codigo_sri_confirmado: false` mantiene el borrador sin efecto.

## Ejemplo de alcance ICE específico

Cada producto indica cuántos litros de alcohol puro comprende una unidad comercial. La tarifa se expresa por esa unidad gravable.

```json
{
  "tipo_impuesto": "ICE",
  "componente": "ESPECIFICO",
  "codigo_impuesto_sri": "3",
  "codigo_porcentaje_sri": "CODIGO_CONFIRMADO_SRI",
  "codigo_sri_confirmado": false,
  "tarifa": "1.560000",
  "productos": [
    {
      "producto_id": "UUID_CERVEZA",
      "factor_cantidad": "0.02500000",
      "unidad_gravable": "LITRO_ALCOHOL_PURO"
    }
  ]
}
```

No actives una medida ICE hasta corroborar en la fuente oficial la tarifa, base/unidad, código y fechas exactas.

## Venta y trazabilidad

Al registrar una venta, el backend selecciona medidas activas compatibles por empresa, fecha de emisión, producto y componente. El cliente no puede enviar un ID de medida o cambiar la tarifa final. El cálculo se refleja en el total IVA/ICE, el subtotal IVA 8% cuando corresponda y el snapshot de cada línea (`medida_temporal_id`, referencia legal, componente, unidad/cantidad gravable, código, tarifa y valor). Cambiar o desactivar después una medida no modifica ventas guardadas ni autorizadas.

Los componentes ICE específicos solo se procesan en ventas. Compras, retenciones, inventario y cartera no tienen una regla temporal paralela; inventario y CxC reciben únicamente sus movimientos/totales comerciales existentes.
