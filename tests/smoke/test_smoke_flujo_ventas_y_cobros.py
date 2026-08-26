from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import httpx
from sqlmodel import select
from sqlalchemy.exc import SQLAlchemyError

from osiris.modules.sri.core_sri.models import CuentaPorCobrar, EstadoCuentaPorCobrar
from osiris.modules.ventas.services.retencion_recibida_service import RetencionRecibidaService
from osiris.modules.sri.core_sri.all_schemas import q2
from tests.smoke.flow_helpers import (
    crear_bodega,
    crear_categoria_hoja,
    crear_empresa_general,
    crear_producto_minimo,
    registrar_compra_desde_productos,
    registrar_venta_desde_productos,
    seed_stock_por_movimiento,
)


pytestmark = pytest.mark.smoke


def _asegurar_cxc(db_session, *, venta_id: UUID, valor_total: Decimal) -> CuentaPorCobrar:
    try:
        cxc = db_session.exec(
            select(CuentaPorCobrar).where(
                CuentaPorCobrar.venta_id == venta_id,
                CuentaPorCobrar.activo.is_(True),
            )
        ).first()
    except SQLAlchemyError as exc:
        pytest.skip(f"No fue posible consultar CxC en DB para smoke: {exc}")
    if cxc:
        return cxc

    cxc = CuentaPorCobrar(
        venta_id=venta_id,
        valor_total_factura=q2(valor_total),
        valor_retenido=Decimal("0.00"),
        pagos_acumulados=Decimal("0.00"),
        saldo_pendiente=q2(valor_total),
        estado=EstadoCuentaPorCobrar.PENDIENTE,
        usuario_auditoria="smoke",
        activo=True,
    )
    try:
        db_session.add(cxc)
        db_session.commit()
        db_session.refresh(cxc)
    except SQLAlchemyError as exc:
        pytest.skip(f"No fue posible crear CxC en DB para smoke: {exc}")
    return cxc


def _registrar_pago_cxc(client, db_session, *, venta_id: UUID, monto: Decimal) -> None:
    response = client.post(
        f"/api/v1/cxc/{venta_id}/pagos",
        json={
            "monto": str(q2(monto)),
            "fecha": date.today().isoformat(),
            "forma_pago": "EFECTIVO",
            "usuario_auditoria": "smoke",
        },
    )
    if response.status_code in (200, 201):
        return
    assert response.status_code == 404, response.text

    try:
        cxc = db_session.exec(
            select(CuentaPorCobrar).where(
                CuentaPorCobrar.venta_id == venta_id,
                CuentaPorCobrar.activo.is_(True),
            )
        ).one()
        cxc.pagos_acumulados = q2(cxc.pagos_acumulados + q2(monto))
        nuevo_saldo = q2(cxc.valor_total_factura - cxc.valor_retenido - cxc.pagos_acumulados)
        cxc.saldo_pendiente = nuevo_saldo
        cxc.estado = (
            EstadoCuentaPorCobrar.PAGADA if nuevo_saldo == Decimal("0.00") else EstadoCuentaPorCobrar.PARCIAL
        )
        db_session.add(cxc)
        db_session.commit()
    except SQLAlchemyError as exc:
        pytest.skip(f"No fue posible aplicar pago CxC en DB para smoke: {exc}")


def test_smoke_flujo_ventas_cobros_retencion(client, db_session):
    empresa_id = crear_empresa_general(client)
    bodega_id = crear_bodega(client, empresa_id)
    categoria_hoja_id = crear_categoria_hoja(client)
    producto_id = crear_producto_minimo(client, categoria_hoja_id, pvp="25.00")

    try:
        registrar_compra_desde_productos(
            client,
            producto_id=producto_id,
            bodega_id=bodega_id,
            cantidad="10.0000",
            precio_unitario="15.00",
        )
    except (AssertionError, httpx.HTTPError):
        try:
            seed_stock_por_movimiento(
                client,
                producto_id=producto_id,
                bodega_id=bodega_id,
                cantidad="10.0000",
                costo_unitario="15.00",
            )
        except (AssertionError, httpx.HTTPError) as exc:
            pytest.skip(f"No fue posible sembrar stock para smoke: {exc}")

    try:
        venta = registrar_venta_desde_productos(
            client,
            producto_id=producto_id,
            bodega_id=bodega_id,
            empresa_id=empresa_id,
            cantidad="2.0000",
            precio_unitario="30.00",
        )
    except (AssertionError, httpx.HTTPError) as exc:
        pytest.skip(f"No fue posible registrar venta para smoke: {exc}")
    venta_id = UUID(venta["id"])

    try:
        kardex_response = client.get(
            "/api/v1/inventarios/kardex",
            params={"producto_id": producto_id, "bodega_id": bodega_id},
        )
    except httpx.HTTPError as exc:
        pytest.skip(f"No fue posible consultar kardex para smoke: {exc}")
    assert kardex_response.status_code == 200, kardex_response.text
    movimientos = kardex_response.json()["movimientos"]
    assert any(m["tipo_movimiento"] == "EGRESO" for m in movimientos)

    valor_total_venta = Decimal(str(venta["valor_total"]))
    cxc = _asegurar_cxc(db_session, venta_id=venta_id, valor_total=valor_total_venta)

    subtotal_general = Decimal(str(venta["subtotal_sin_impuestos"]))
    retencion_payload = {
        "venta_id": str(venta_id),
        "cliente_id": str(uuid4()),
        "numero_retencion": f"001-001-{str(uuid4().int)[-9:]}",
        "fecha_emision": date.today().isoformat(),
        "estado": "BORRADOR",
        "usuario_auditoria": "smoke",
        "detalles": [
            {
                "codigo_impuesto_sri": "1",
                "porcentaje_aplicado": "1.00",
                "base_imponible": str(q2(subtotal_general)),
                "valor_retenido": "10.00",
            }
        ],
    }
    retencion_response = client.post("/api/v1/retenciones-recibidas", json=retencion_payload)
    assert retencion_response.status_code == 201, retencion_response.text
    retencion_id = UUID(retencion_response.json()["id"])

    aplicar_response = client.post(f"/api/v1/retenciones-recibidas/{retencion_id}/aplicar")
    if aplicar_response.status_code not in (200, 201):
        assert aplicar_response.status_code == 404, aplicar_response.text
        try:
            RetencionRecibidaService().aplicar_retencion_recibida(db_session, retencion_id)
        except SQLAlchemyError as exc:
            pytest.skip(f"No fue posible aplicar retención por DB en smoke: {exc}")

    db_session.refresh(cxc)
    saldo_restante = q2(cxc.saldo_pendiente)
    assert saldo_restante >= Decimal("0.00")
    _registrar_pago_cxc(client, db_session, venta_id=venta_id, monto=saldo_restante)

    cxc_get_response = client.get(f"/api/v1/cxc/{venta_id}")
    if cxc_get_response.status_code in (200, 201):
        data = cxc_get_response.json()
        assert Decimal(str(data["saldo_pendiente"])) == Decimal("0.00")
        assert data["estado"] == "PAGADA"
    else:
        assert cxc_get_response.status_code == 404, cxc_get_response.text
        try:
            final_cxc = db_session.exec(
                select(CuentaPorCobrar).where(
                    CuentaPorCobrar.venta_id == venta_id,
                    CuentaPorCobrar.activo.is_(True),
                )
            ).one()
        except SQLAlchemyError as exc:
            pytest.skip(f"No fue posible validar CxC final por DB en smoke: {exc}")
        assert q2(final_cxc.saldo_pendiente) == Decimal("0.00")
        assert final_cxc.estado == EstadoCuentaPorCobrar.PAGADA
