from __future__ import annotations

from datetime import date
from decimal import Decimal
from time import sleep
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlmodel import select

from osiris.modules.sri.core_sri.models import (
    DocumentoElectronico,
    EstadoDocumentoElectronico,
    TipoDocumentoElectronico,
)
from osiris.modules.sri.facturacion_electronica.router import (
    orquestador_fe_service as fe_orquestador_router_service,
)
from osiris.modules.ventas.router import venta_service as venta_router_service
from osiris.modules.inventario.producto.entity import Producto, ProductoImpuesto, TipoProducto
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo
from tests.smoke.flow_helpers import (
    crear_bodega,
    crear_empresa_general,
    seed_stock_por_movimiento,
)


pytestmark = pytest.mark.smoke


@pytest.mark.smoke
def test_smoke_flujo_ventas(client, db_session):
    empresa_id = crear_empresa_general(client)
    bodega_id = crear_bodega(client, empresa_id)
    iva = db_session.exec(
        select(ImpuestoCatalogo).where(
            ImpuestoCatalogo.codigo_sri == "2",
            ImpuestoCatalogo.activo.is_(True),
        )
    ).first()
    assert iva is not None
    producto = Producto(
        nombre="SMOKE-PRODUCTO-E6-6",
        descripcion="Producto smoke ventas",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("30.00"),
        cantidad=0,
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(producto)
    db_session.flush()
    db_session.add(
        ProductoImpuesto(
            producto_id=producto.id,
            impuesto_catalogo_id=iva.id,
            codigo_impuesto_sri="2",
            codigo_porcentaje_sri="0",
            tarifa=Decimal("0.0000"),
            usuario_auditoria="smoke",
            activo=True,
        )
    )
    db_session.commit()
    producto_id = str(producto.id)

    cantidad_venta = Decimal("2.0000")
    seed_stock_por_movimiento(
        client,
        producto_id=producto_id,
        bodega_id=bodega_id,
        cantidad="10.0000",
        costo_unitario="12.00",
    )

    venta_payload = {
        "empresa_id": empresa_id,
        "fecha_emision": date.today().isoformat(),
        "bodega_id": bodega_id,
        "tipo_identificacion_comprador": "RUC",
        "identificacion_comprador": "1790012345001",
        "forma_pago": "EFECTIVO",
        "tipo_emision": "ELECTRONICA",
        "regimen_emisor": "GENERAL",
        "usuario_auditoria": "smoke",
        "detalles": [
            {
                "producto_id": producto_id,
                "descripcion": "Detalle venta smoke",
                "cantidad": str(cantidad_venta),
                "precio_unitario": "30.00",
                "descuento": "0.00",
                "es_actividad_excluida": False,
                "impuestos": [
                    {
                        "tipo_impuesto": "IVA",
                        "codigo_impuesto_sri": "2",
                        "codigo_porcentaje_sri": "0",
                        "tarifa": "0.00",
                    }
                ],
            }
        ],
    }

    with patch("osiris.modules.sri.facturacion_electronica.services.venta_sri_async_service.ManejadorXML") as mock_xml, patch(
        "osiris.modules.sri.facturacion_electronica.services.venta_sri_async_service.SRIService"
    ) as mock_sri, patch("starlette.background.BackgroundTasks.add_task", return_value=None):
        venta_router_service.venta_sri_async_service.db_engine = db_session.get_bind()
        venta_router_service.orquestador_fe_service.db_engine = db_session.get_bind()
        venta_router_service.orquestador_fe_service.venta_sri_service.db_engine = db_session.get_bind()
        fe_orquestador_router_service.db_engine = db_session.get_bind()
        fe_orquestador_router_service.venta_sri_service.db_engine = db_session.get_bind()
        mock_xml.return_value.firmar_y_guardar_xml.return_value = b"<factura/>"
        mock_sri.return_value.enviar_recepcion.return_value = {"estado": "RECIBIDA", "mensaje": "OK"}
        mock_sri.return_value.consultar_autorizacion.return_value = {
            "estado": "AUTORIZADO",
            "mensaje": "AUTORIZADO",
        }

        crear_venta = client.post("/api/v1/ventas", json=venta_payload)
        assert crear_venta.status_code == 201, crear_venta.text
        venta_data = crear_venta.json()
        venta_id = UUID(venta_data["id"])
        assert venta_data["estado"] == "EMITIDA"

        documento_encolado = db_session.exec(
            select(DocumentoElectronico).where(
                DocumentoElectronico.tipo_documento == TipoDocumentoElectronico.FACTURA,
                DocumentoElectronico.referencia_id == venta_id,
                DocumentoElectronico.activo.is_(True),
            )
        ).one_or_none()
        assert documento_encolado is not None
        assert documento_encolado.estado_sri == EstadoDocumentoElectronico.EN_COLA

        procesar_cola = client.post("/api/v1/fe/procesar-cola")
        assert procesar_cola.status_code == 200, procesar_cola.text

        db_session.expire_all()
        documento_autorizado = db_session.exec(
            select(DocumentoElectronico).where(
                DocumentoElectronico.id == documento_encolado.id,
                DocumentoElectronico.activo.is_(True),
            )
        ).one_or_none()
        assert documento_autorizado is not None
        assert documento_autorizado.estado_sri == EstadoDocumentoElectronico.AUTORIZADO

    kardex = client.get(
        "/api/v1/inventarios/kardex",
        params={"producto_id": producto_id, "bodega_id": bodega_id},
    )
    assert kardex.status_code == 200, kardex.text
    movimientos = kardex.json()["movimientos"]
    assert any(m["tipo_movimiento"] == "EGRESO" for m in movimientos)
    saldo_final = Decimal(str(movimientos[-1]["saldo_cantidad"]))
    assert saldo_final == Decimal("8.0000")

    venta_get = None
    for _ in range(5):
        venta_get = client.get(f"/api/v1/ventas/{venta_id}")
        assert venta_get.status_code == 200, venta_get.text
        if venta_get.json().get("estado_sri") == "AUTORIZADO":
            break
        sleep(0.05)
    assert venta_get is not None
    assert venta_get.json()["estado_sri"] == "AUTORIZADO"

    cxc_get = client.get(f"/api/v1/cxc/{venta_id}")
    assert cxc_get.status_code == 200, cxc_get.text
    cxc_data = cxc_get.json()
    saldo = Decimal(str(cxc_data["saldo_pendiente"]))
    assert saldo > Decimal("0.00")

    pago = client.post(
        f"/api/v1/cxc/{venta_id}/pagos",
        json={
            "monto": str(saldo),
            "fecha": date.today().isoformat(),
            "forma_pago_sri": "EFECTIVO",
            "usuario_auditoria": "smoke",
        },
    )
    assert pago.status_code == 201, pago.text

    cxc_final = client.get(f"/api/v1/cxc/{venta_id}")
    assert cxc_final.status_code == 200, cxc_final.text
    cxc_final_data = cxc_final.json()
    assert cxc_final_data["estado"] == "PAGADA"
    assert Decimal(str(cxc_final_data["saldo_pendiente"])) == Decimal("0.00")
