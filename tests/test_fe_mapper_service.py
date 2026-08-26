from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from osiris.modules.common.empresa.entity import RegimenTributario
from osiris.modules.sri.facturacion_electronica.services.fe_mapper_service import FEMapperService
from osiris.modules.sri.core_sri.all_schemas import (
    VentaDetalleImpuestoSnapshotRead,
    VentaDetalleRead,
    VentaRead,
)


def test_fe_mapper_agrupa_total_con_impuestos_desde_snapshot():
    mapper = FEMapperService()

    venta = VentaRead(
        id=uuid4(),
        fecha_emision=date(2026, 2, 19),
        tipo_identificacion_comprador="RUC",
        identificacion_comprador="1790012345001",
        forma_pago="EFECTIVO",
        subtotal_sin_impuestos=Decimal("110.00"),
        subtotal_12=Decimal("110.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("0.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("13.50"),
        monto_ice=Decimal("2.50"),
        valor_total=Decimal("126.00"),
        detalles=[
            VentaDetalleRead(
                producto_id=uuid4(),
                descripcion="DET 1",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                descuento=Decimal("0"),
                subtotal_sin_impuesto=Decimal("100.00"),
                impuestos=[
                    VentaDetalleImpuestoSnapshotRead(
                        tipo_impuesto="IVA",
                        codigo_impuesto_sri="2",
                        codigo_porcentaje_sri="2",
                        tarifa=Decimal("12"),
                        base_imponible=Decimal("102.50"),
                        valor_impuesto=Decimal("12.30"),
                    ),
                    VentaDetalleImpuestoSnapshotRead(
                        tipo_impuesto="ICE",
                        codigo_impuesto_sri="3",
                        codigo_porcentaje_sri="305",
                        tarifa=Decimal("2.5"),
                        base_imponible=Decimal("100.00"),
                        valor_impuesto=Decimal("2.50"),
                    ),
                ],
            ),
            VentaDetalleRead(
                producto_id=uuid4(),
                descripcion="DET 2",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("10"),
                descuento=Decimal("0"),
                subtotal_sin_impuesto=Decimal("10.00"),
                impuestos=[
                    VentaDetalleImpuestoSnapshotRead(
                        tipo_impuesto="IVA",
                        codigo_impuesto_sri="2",
                        codigo_porcentaje_sri="2",
                        tarifa=Decimal("12"),
                        base_imponible=Decimal("10.00"),
                        valor_impuesto=Decimal("1.20"),
                    )
                ],
            ),
        ],
    )

    payload = mapper.venta_to_fe_payload(venta)
    assert payload["infoFactura"]["importeTotal"] == "126.00"
    assert payload["infoFactura"]["pagos"][0]["formaPago"] == "01"
    assert payload["infoTributaria"]["tipoIdentificacionComprador"] == "04"

    total_con_impuestos = payload["infoFactura"]["totalConImpuestos"]
    assert {"codigo": "2", "codigoPorcentaje": "2", "baseImponible": "112.50", "valor": "13.50"} in total_con_impuestos
    assert {"codigo": "3", "codigoPorcentaje": "305", "baseImponible": "100.00", "valor": "2.50"} in total_con_impuestos


def test_fe_mapper_falla_si_impuestos_detalle_no_cuadran_con_cabecera():
    mapper = FEMapperService()
    venta = VentaRead(
        id=uuid4(),
        fecha_emision=date(2026, 2, 19),
        tipo_identificacion_comprador="RUC",
        identificacion_comprador="1790012345001",
        forma_pago="EFECTIVO",
        subtotal_sin_impuestos=Decimal("100.00"),
        subtotal_12=Decimal("100.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("0.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("11.99"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("111.99"),
        detalles=[
            VentaDetalleRead(
                producto_id=uuid4(),
                descripcion="DET",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                descuento=Decimal("0"),
                subtotal_sin_impuesto=Decimal("100.00"),
                impuestos=[
                    VentaDetalleImpuestoSnapshotRead(
                        tipo_impuesto="IVA",
                        codigo_impuesto_sri="2",
                        codigo_porcentaje_sri="2",
                        tarifa=Decimal("12"),
                        base_imponible=Decimal("100.00"),
                        valor_impuesto=Decimal("12.00"),
                    )
                ],
            )
        ],
    )

    with pytest.raises(ValueError) as exc:
        mapper.venta_to_fe_payload(venta)
    assert "cabecera" in str(exc.value).lower()


def test_fe_mapper_inyecta_leyenda_rimpe_negocio_popular_en_info_adicional():
    mapper = FEMapperService()
    venta = VentaRead(
        id=uuid4(),
        fecha_emision=date(2026, 2, 19),
        tipo_identificacion_comprador="RUC",
        identificacion_comprador="1790012345001",
        forma_pago="EFECTIVO",
        regimen_emisor=RegimenTributario.RIMPE_NEGOCIO_POPULAR,
        subtotal_sin_impuestos=Decimal("100.00"),
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("100.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("100.00"),
        detalles=[
            VentaDetalleRead(
                producto_id=uuid4(),
                descripcion="DET",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                descuento=Decimal("0"),
                subtotal_sin_impuesto=Decimal("100.00"),
                impuestos=[
                    VentaDetalleImpuestoSnapshotRead(
                        tipo_impuesto="IVA",
                        codigo_impuesto_sri="2",
                        codigo_porcentaje_sri="0",
                        tarifa=Decimal("0"),
                        base_imponible=Decimal("100.00"),
                        valor_impuesto=Decimal("0.00"),
                    )
                ],
            )
        ],
    )

    payload = mapper.venta_to_fe_payload(venta)
    assert payload["infoAdicional"]["campoAdicional"][0]["nombre"] == "Contribuyente"
    assert (
        payload["infoAdicional"]["campoAdicional"][0]["valor"]
        == "Contribuyente Negocio Popular - Régimen RIMPE"
    )


def test_rimpe_np_emite_electronica_leyenda_y_cero_iva(monkeypatch):
    class FakeSettings:
        FEEC_AMBIENTE = "pruebas"
        FEEC_TIPO_EMISION = "1"

    monkeypatch.setattr(
        "osiris.modules.sri.facturacion_electronica.services.fe_mapper_service.get_settings",
        lambda: FakeSettings(),
    )

    mapper = FEMapperService()
    venta = VentaRead(
        id=uuid4(),
        fecha_emision=date(2026, 2, 21),
        tipo_identificacion_comprador="RUC",
        identificacion_comprador="1790012345001",
        forma_pago="EFECTIVO",
        tipo_emision="ELECTRONICA",
        regimen_emisor=RegimenTributario.RIMPE_NEGOCIO_POPULAR,
        subtotal_sin_impuestos=Decimal("100.00"),
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("100.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("100.00"),
        detalles=[
            VentaDetalleRead(
                producto_id=uuid4(),
                descripcion="DET",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                descuento=Decimal("0"),
                subtotal_sin_impuesto=Decimal("100.00"),
                impuestos=[
                    VentaDetalleImpuestoSnapshotRead(
                        tipo_impuesto="IVA",
                        codigo_impuesto_sri="2",
                        codigo_porcentaje_sri="0",
                        tarifa=Decimal("0"),
                        base_imponible=Decimal("100.00"),
                        valor_impuesto=Decimal("0.00"),
                    )
                ],
            )
        ],
    )

    payload = mapper.venta_to_fe_ec_payload(
        venta,
        ruc_emisor="1790012345001",
        razon_social="Empresa RIMPE",
        nombre_comercial="Empresa RIMPE",
        dir_matriz="Quito",
        obligado_contabilidad=False,
    )

    assert payload["infoTributaria"]["codDoc"] == "01"
    assert {
        "nombre": "Contribuyente",
        "valor": "Contribuyente Negocio Popular - Régimen RIMPE",
    } in payload["infoAdicional"]["campoAdicional"]
