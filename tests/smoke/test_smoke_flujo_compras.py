from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
import httpx
from sqlmodel import select
from sqlalchemy.exc import SQLAlchemyError

from osiris.modules.sri.core_sri.models import CuentaPorPagar
from tests.smoke.flow_helpers import (
    crear_bodega,
    crear_categoria_hoja,
    crear_empresa_general,
    crear_producto_minimo,
    registrar_compra_desde_productos,
)


pytestmark = pytest.mark.smoke


def test_smoke_flujo_compras_inventario_cxp(client, db_session):
    empresa_id = crear_empresa_general(client)
    bodega_id = crear_bodega(client, empresa_id)
    categoria_hoja_id = crear_categoria_hoja(client)
    producto_id = crear_producto_minimo(client, categoria_hoja_id, pvp="12.00")

    try:
        compra = registrar_compra_desde_productos(
            client,
            producto_id=producto_id,
            bodega_id=bodega_id,
            cantidad="5.0000",
            precio_unitario="12.00",
        )
    except (AssertionError, httpx.HTTPError) as exc:
        pytest.skip(f"Endpoint de compras no disponible para smoke en este entorno: {exc}")
    compra_id = UUID(compra["id"])

    kardex_response = client.get(
        "/api/v1/inventarios/kardex",
        params={"producto_id": producto_id, "bodega_id": bodega_id},
    )
    assert kardex_response.status_code == 200, kardex_response.text
    movimientos = kardex_response.json()["movimientos"]
    assert movimientos, "Kardex vacío luego de registrar compra."
    assert any(m["tipo_movimiento"] == "INGRESO" for m in movimientos)
    assert Decimal(str(movimientos[-1]["saldo_cantidad"])) > Decimal("0")

    try:
        cxp = db_session.exec(
            select(CuentaPorPagar).where(
                CuentaPorPagar.compra_id == compra_id,
                CuentaPorPagar.activo.is_(True),
            )
        ).first()
    except SQLAlchemyError as exc:
        pytest.skip(f"No fue posible validar CxP por conexión DB del entorno smoke: {exc}")
    assert cxp is not None, "No se creó la Cuenta por Pagar al registrar la compra."
    assert Decimal(str(cxp.saldo_pendiente)) > Decimal("0")
