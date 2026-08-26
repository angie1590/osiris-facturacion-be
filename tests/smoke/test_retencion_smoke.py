from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from osiris.modules.sri.core_sri.all_schemas import q2
from tests.smoke.flow_helpers import (
    crear_bodega,
    crear_categoria_hoja,
    crear_empresa_general,
    crear_producto_minimo,
    registrar_venta_desde_productos,
    seed_stock_por_movimiento,
)


pytestmark = pytest.mark.smoke


def test_retencion_recibida_smoke(client):
    empresa_id = crear_empresa_general(client)
    bodega_id = crear_bodega(client, empresa_id)
    categoria_hoja_id = crear_categoria_hoja(client)
    producto_id = crear_producto_minimo(client, categoria_hoja_id, pvp="30.00")

    seed_stock_por_movimiento(
        client,
        producto_id=producto_id,
        bodega_id=bodega_id,
        cantidad="5.0000",
        costo_unitario="20.00",
    )

    venta = registrar_venta_desde_productos(
        client,
        producto_id=producto_id,
        bodega_id=bodega_id,
        empresa_id=empresa_id,
        cantidad="1.0000",
        precio_unitario="30.00",
    )

    subtotal_general = q2(Decimal(str(venta["subtotal_sin_impuestos"])))
    payload = {
        "venta_id": venta["id"],
        "cliente_id": str(uuid4()),
        "numero_retencion": f"001-001-{str(uuid4().int)[-9:]}",
        "fecha_emision": date.today().isoformat(),
        "estado": "BORRADOR",
        "usuario_auditoria": "smoke",
        "detalles": [
            {
                "codigo_impuesto_sri": "1",
                "porcentaje_aplicado": "1.00",
                "base_imponible": str(subtotal_general),
                "valor_retenido": "0.30",
            }
        ],
    }
    response = client.post("/api/v1/retenciones-recibidas", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["estado"] == "BORRADOR"
    assert Decimal(str(body["total_retenido"])) > Decimal("0")
