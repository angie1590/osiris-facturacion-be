from __future__ import annotations

from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from osiris.core.audit_context import reset_current_company_id, set_current_company_id
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.sri.core_sri.models import VentaDetalleImpuesto
from osiris.modules.sri.core_sri.all_schemas import VentaRegistroCreate, VentaCompraDetalleRegistroCreate
from osiris.modules.ventas.services.venta_service import VentaService
from osiris.modules.inventario.producto.entity import Producto, ProductoImpuesto, TipoProducto
from osiris.modules.sri.impuesto_catalogo.entity import AplicaA, ImpuestoCatalogo, TipoImpuesto


def test_venta_historica_mantiene_snapshot_si_cambia_producto_impuesto():
    session = MagicMock()
    empresa_id = uuid4()
    empresa = Empresa(id=empresa_id, razon_social="Empresa", ruc="1790012345001", direccion_matriz="Direccion", tipo_contribuyente_id="01", usuario_auditoria="tester", activo=True)

    producto = Producto(
        nombre="Producto Snapshot",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    impuesto = ImpuestoCatalogo(
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="2",
        descripcion="IVA 12%",
        vigente_desde=date(2020, 1, 1),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=Decimal("12.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    producto_impuesto = ProductoImpuesto(
        producto_id=producto.id,
        empresa_id=empresa_id,
        impuesto_catalogo_id=impuesto.id,
        codigo_impuesto_sri="2",
        codigo_porcentaje_sri="2",
        tarifa=Decimal("12.00"),
        usuario_auditoria="tester",
        activo=True,
    )

    def mock_get(model, item_id):
        if model is Producto and item_id == producto.id:
            return producto
        if model is Empresa and item_id == empresa_id:
            return empresa
        return None

    session.get.side_effect = mock_get
    exec_result = MagicMock()
    exec_result.all.return_value = [producto_impuesto]
    session.exec.return_value = exec_result

    service = VentaService()
    token = set_current_company_id(str(empresa_id))
    try:
        service.registrar_venta_desde_productos(
            session,
            VentaRegistroCreate(
                tipo_identificacion_comprador="RUC",
                identificacion_comprador="1790012345001",
                forma_pago="EFECTIVO",
                usuario_auditoria="tester",
                detalles=[
                    VentaCompraDetalleRegistroCreate(
                        producto_id=producto.id,
                        descripcion="Producto Snapshot",
                        cantidad=Decimal("1"),
                        precio_unitario=Decimal("10.00"),
                    )
                ],
            ),
        )
    finally:
        reset_current_company_id(token)

    # Capturar el snapshot persistido en la venta
    added_objects = [call.args[0] for call in session.add.call_args_list if call.args]
    snapshot = next(obj for obj in added_objects if isinstance(obj, VentaDetalleImpuesto))
    assert snapshot.codigo_porcentaje_sri == "2"
    assert snapshot.tarifa == Decimal("12.00")
    assert snapshot.valor_impuesto == Decimal("1.20")

    # Cambio posterior del impuesto en producto no altera el snapshot historico
    producto_impuesto.codigo_porcentaje_sri = "4"
    producto_impuesto.tarifa = Decimal("15.00")
    assert snapshot.codigo_porcentaje_sri == "2"
    assert snapshot.tarifa == Decimal("12.00")


def test_snapshot_congela_base_iva_con_ice_en_detalle():
    session = MagicMock()
    empresa_id = uuid4()
    empresa = Empresa(id=empresa_id, razon_social="Empresa", ruc="1790012345001", direccion_matriz="Direccion", tipo_contribuyente_id="01", usuario_auditoria="tester", activo=True)

    producto = Producto(
        nombre="Producto ICE+IVA",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    impuesto = ImpuestoCatalogo(
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="2",
        descripcion="IVA 12%",
        vigente_desde=date(2020, 1, 1),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=Decimal("12.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    impuesto_ice = ImpuestoCatalogo(
        tipo_impuesto=TipoImpuesto.ICE,
        codigo_tipo_impuesto="3",
        codigo_sri="305",
        descripcion="ICE 5%",
        vigente_desde=date(2020, 1, 1),
        aplica_a=AplicaA.AMBOS,
        tarifa_ad_valorem=Decimal("5.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    producto_impuesto_iva = ProductoImpuesto(
        producto_id=producto.id,
        empresa_id=empresa_id,
        impuesto_catalogo_id=impuesto.id,
        codigo_impuesto_sri="2",
        codigo_porcentaje_sri="2",
        tarifa=Decimal("12.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    producto_impuesto_ice = ProductoImpuesto(
        producto_id=producto.id,
        empresa_id=empresa_id,
        impuesto_catalogo_id=impuesto_ice.id,
        codigo_impuesto_sri="3",
        codigo_porcentaje_sri="305",
        tarifa=Decimal("5.00"),
        usuario_auditoria="tester",
        activo=True,
    )

    def mock_get(model, item_id):
        if model is Producto and item_id == producto.id:
            return producto
        if model is Empresa and item_id == empresa_id:
            return empresa
        return None

    session.get.side_effect = mock_get
    exec_result = MagicMock()
    exec_result.all.return_value = [producto_impuesto_iva, producto_impuesto_ice]
    session.exec.return_value = exec_result

    service = VentaService()
    token = set_current_company_id(str(empresa_id))
    try:
        service.registrar_venta_desde_productos(
            session,
            VentaRegistroCreate(
                tipo_identificacion_comprador="RUC",
                identificacion_comprador="1790012345001",
                forma_pago="EFECTIVO",
                usuario_auditoria="tester",
                detalles=[
                    VentaCompraDetalleRegistroCreate(
                        producto_id=producto.id,
                        descripcion="Producto ICE+IVA",
                        cantidad=Decimal("1"),
                        precio_unitario=Decimal("10.00"),
                    )
                ],
            ),
        )
    finally:
        reset_current_company_id(token)

    added_objects = [call.args[0] for call in session.add.call_args_list if call.args]
    snapshots = [obj for obj in added_objects if isinstance(obj, VentaDetalleImpuesto)]

    assert len(snapshots) == 2
    snapshot_iva = next(s for s in snapshots if s.codigo_impuesto_sri == "2")
    snapshot_ice = next(s for s in snapshots if s.codigo_impuesto_sri == "3")

    assert snapshot_ice.base_imponible == Decimal("10.00")
    assert snapshot_ice.valor_impuesto == Decimal("0.50")
    assert snapshot_iva.base_imponible == Decimal("10.50")
    assert snapshot_iva.valor_impuesto == Decimal("1.26")


def test_venta_rechaza_bodega_de_empresa_distinta_antes_de_snapshotear():
    session = MagicMock()
    company_id = uuid4()
    foreign_warehouse = type("Warehouse", (), {"id": uuid4(), "empresa_id": uuid4(), "activo": True})()
    session.get.return_value = foreign_warehouse
    product_id = uuid4()
    token = set_current_company_id(str(company_id))
    try:
        with pytest.raises(HTTPException, match="bodega no pertenece a la empresa autenticada") as exc_info:
            VentaService().hidratar_venta_desde_productos(
                session,
                VentaRegistroCreate(
                    empresa_id=company_id,
                    bodega_id=foreign_warehouse.id,
                    tipo_identificacion_comprador="RUC",
                    identificacion_comprador="1790012345001",
                    forma_pago="EFECTIVO",
                    usuario_auditoria="tester",
                    detalles=[
                        VentaCompraDetalleRegistroCreate(
                            producto_id=product_id,
                            descripcion="Producto compartido",
                            cantidad=Decimal("1"),
                            precio_unitario=Decimal("10.00"),
                        )
                    ],
                ),
            )
        assert exc_info.value.status_code == 403
        session.get.assert_called_once_with(Bodega, foreign_warehouse.id)
        session.exec.assert_not_called()
    finally:
        reset_current_company_id(token)
