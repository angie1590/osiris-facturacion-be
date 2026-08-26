from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from osiris.modules.common.empresa.entity import RegimenTributario
from osiris.modules.sri.core_sri.all_schemas import (
    CompraCreate,
    ImpuestoAplicadoInput,
    VentaCompraDetalleCreate,
    VentaCreate,
)


def _iva12() -> ImpuestoAplicadoInput:
    return ImpuestoAplicadoInput(
        tipo_impuesto="IVA",
        codigo_impuesto_sri="2",
        codigo_porcentaje_sri="2",
        tarifa=Decimal("12"),
    )


def _iva15() -> ImpuestoAplicadoInput:
    return ImpuestoAplicadoInput(
        tipo_impuesto="IVA",
        codigo_impuesto_sri="2",
        codigo_porcentaje_sri="4",
        tarifa=Decimal("15"),
    )


def _iva0() -> ImpuestoAplicadoInput:
    return ImpuestoAplicadoInput(
        tipo_impuesto="IVA",
        codigo_impuesto_sri="2",
        codigo_porcentaje_sri="0",
        tarifa=Decimal("0"),
    )


def _ice5() -> ImpuestoAplicadoInput:
    return ImpuestoAplicadoInput(
        tipo_impuesto="ICE",
        codigo_impuesto_sri="3",
        codigo_porcentaje_sri="305",
        tarifa=Decimal("5"),
    )


def test_venta_create_calcula_totales_e_impuestos_al_centavo():
    venta = VentaCreate(
        tipo_identificacion_comprador="RUC",
        identificacion_comprador="1790012345001",
        forma_pago="EFECTIVO",
        usuario_auditoria="tester",
        detalles=[
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="A",
                cantidad=Decimal("2"),
                precio_unitario=Decimal("10"),
                impuestos=[_iva12()],
            ),
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="B",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                descuento=Decimal("10"),
                impuestos=[_iva15(), _ice5()],
            ),
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="C",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("50"),
                impuestos=[_iva0()],
            ),
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="D",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("30"),
                impuestos=[],
            ),
        ],
    )

    assert venta.subtotal_sin_impuestos == Decimal("190.00")
    assert venta.subtotal_12 == Decimal("20.00")
    assert venta.subtotal_15 == Decimal("90.00")
    assert venta.subtotal_0 == Decimal("50.00")
    assert venta.subtotal_no_objeto == Decimal("30.00")
    assert venta.monto_iva == Decimal("16.58")
    assert venta.monto_ice == Decimal("4.50")
    assert venta.valor_total == Decimal("211.08")


def test_venta_calculo_totales_exactos():
    venta = VentaCreate(
        tipo_identificacion_comprador="RUC",
        identificacion_comprador="1790012345001",
        forma_pago="EFECTIVO",
        usuario_auditoria="tester",
        detalles=[
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="Servicio 15%",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100.00"),
                impuestos=[_iva15()],
            )
        ],
    )

    assert venta.subtotal_sin_impuestos == Decimal("100.00")
    assert venta.subtotal_15 == Decimal("100.00")
    assert venta.monto_iva == Decimal("15.00")
    assert venta.total == Decimal("115.00")


def test_compra_create_calcula_totales_redondeados():
    compra = CompraCreate(
        proveedor_id=uuid4(),
        secuencial_factura="001-001-123456789",
        autorizacion_sri="1" * 49,
        tipo_identificacion_proveedor="RUC",
        identificacion_proveedor="1790099988001",
        sustento_tributario="01",
        forma_pago="TRANSFERENCIA",
        usuario_auditoria="tester",
        detalles=[
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="INSUMO",
                cantidad=Decimal("3"),
                precio_unitario=Decimal("0.99"),
                impuestos=[_iva12()],
            ),
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="SERVICIO",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("10"),
                impuestos=[],
            ),
        ],
    )

    # base1 = 2.97, iva = 0.3564 -> 0.36
    assert compra.subtotal_sin_impuestos == Decimal("12.97")
    assert compra.subtotal_12 == Decimal("2.97")
    assert compra.subtotal_no_objeto == Decimal("10.00")
    assert compra.monto_iva == Decimal("0.36")
    assert compra.monto_ice == Decimal("0.00")
    assert compra.valor_total == Decimal("13.33")


def test_compra_calcula_totales():
    compra = CompraCreate(
        proveedor_id=uuid4(),
        secuencial_factura="001-001-987654321",
        autorizacion_sri="2" * 37,
        tipo_identificacion_proveedor="RUC",
        identificacion_proveedor="1790099988001",
        sustento_tributario="01",
        forma_pago="EFECTIVO",
        usuario_auditoria="tester",
        detalles=[
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="Materia prima",
                cantidad=Decimal("2"),
                precio_unitario=Decimal("10.00"),
                impuestos=[_iva12()],
            ),
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="Servicio exento",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("5.00"),
                impuestos=[],
            ),
        ],
    )

    assert compra.subtotal_sin_impuestos == Decimal("25.00")
    assert compra.subtotal_12 == Decimal("20.00")
    assert compra.subtotal_no_objeto == Decimal("5.00")
    assert compra.monto_iva == Decimal("2.40")
    assert compra.monto_ice == Decimal("0.00")
    assert compra.valor_total == Decimal("27.40")


def test_iva_calcula_base_imponible_sobre_subtotal_mas_ice():
    detalle = VentaCompraDetalleCreate(
        producto_id=uuid4(),
        descripcion="Detalle con ICE",
        cantidad=Decimal("1"),
        precio_unitario=Decimal("100.00"),
        descuento=Decimal("0.00"),
        impuestos=[_iva12(), _ice5()],
    )
    iva = next(i for i in detalle.impuestos if i.tipo_impuesto == "IVA")

    assert detalle.monto_ice_detalle() == Decimal("5.00")
    assert detalle.base_imponible_impuesto(iva) == Decimal("105.00")
    assert detalle.valor_impuesto(iva) == Decimal("12.60")


def test_venta_rimpe_negocio_popular_rechaza_iva_mayor_a_cero_en_actividad_incluyente():
    with pytest.raises(ValidationError) as exc:
        VentaCreate(
            tipo_identificacion_comprador="RUC",
            identificacion_comprador="1790012345001",
            forma_pago="EFECTIVO",
            regimen_emisor=RegimenTributario.RIMPE_NEGOCIO_POPULAR,
            usuario_auditoria="tester",
            detalles=[
                VentaCompraDetalleCreate(
                    producto_id=uuid4(),
                    descripcion="Servicio normal",
                    cantidad=Decimal("1"),
                    precio_unitario=Decimal("10.00"),
                    es_actividad_excluida=False,
                    impuestos=[_iva12()],
                )
            ],
        )

    assert (
        "Los Negocios Populares solo pueden facturar con tarifa 0% de IVA para sus actividades incluyentes"
        in str(exc.value)
    )


def test_venta_rimpe_negocio_popular_permite_iva_si_actividad_excluida():
    venta = VentaCreate(
        tipo_identificacion_comprador="RUC",
        identificacion_comprador="1790012345001",
        forma_pago="EFECTIVO",
        regimen_emisor=RegimenTributario.RIMPE_NEGOCIO_POPULAR,
        usuario_auditoria="tester",
        detalles=[
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="Actividad excluida",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("10.00"),
                es_actividad_excluida=True,
                impuestos=[_iva12()],
            )
        ],
    )
    assert venta.monto_iva == Decimal("1.20")


def test_rimpe_np_bloqueo_iva_electronica():
    with pytest.raises(ValidationError) as exc:
        VentaCreate(
            tipo_identificacion_comprador="RUC",
            identificacion_comprador="1790012345001",
            forma_pago="EFECTIVO",
            tipo_emision="ELECTRONICA",
            regimen_emisor=RegimenTributario.RIMPE_NEGOCIO_POPULAR,
            usuario_auditoria="tester",
            detalles=[
                VentaCompraDetalleCreate(
                    producto_id=uuid4(),
                    descripcion="Servicio gravado",
                    cantidad=Decimal("1"),
                    precio_unitario=Decimal("100.00"),
                    es_actividad_excluida=False,
                    impuestos=[_iva15()],
                )
            ],
        )

    assert "Los Negocios Populares solo pueden facturar electrónicamente con tarifa 0%" in str(exc.value)


def test_venta_rimpe_np_fuerza_nota_venta_fisica_cuando_no_hay_excluidas():
    venta = VentaCreate(
        tipo_identificacion_comprador="RUC",
        identificacion_comprador="1790012345001",
        forma_pago="EFECTIVO",
        regimen_emisor=RegimenTributario.RIMPE_NEGOCIO_POPULAR,
        usuario_auditoria="tester",
        detalles=[
            VentaCompraDetalleCreate(
                producto_id=uuid4(),
                descripcion="Actividad incluyente",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100.00"),
                impuestos=[_iva0()],
            )
        ],
    )

    assert venta.tipo_emision.value == "NOTA_VENTA_FISICA"
