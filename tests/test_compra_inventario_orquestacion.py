from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.compras.services.compra_service import CompraService
from osiris.modules.sri.core_sri.models import (
    Compra,
    CompraDetalle,
    CompraDetalleImpuesto,
    CuentaPorPagar,
    EstadoCompra,
    EstadoCuentaPorPagar,
    TipoImpuestoMVP,
)
from osiris.modules.sri.core_sri.all_schemas import (
    CompraAnularRequest,
    CompraCreate,
    CompraUpdate,
    ImpuestoAplicadoInput,
    VentaCompraDetalleCreate,
)
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.movimientos.models import (
    EstadoMovimientoInventario,
    InventarioStock,
    MovimientoInventario,
    MovimientoInventarioDetalle,
    TipoMovimientoInventario,
)
from osiris.modules.inventario.movimientos.services.movimiento_inventario_service import MovimientoInventarioService
from osiris.modules.inventario.producto.entity import Producto, TipoProducto
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            TipoContribuyente.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            Bodega.__table__,
            CasaComercial.__table__,
            Producto.__table__,
            Compra.__table__,
            CompraDetalle.__table__,
            CompraDetalleImpuesto.__table__,
            CuentaPorPagar.__table__,
            MovimientoInventario.__table__,
            MovimientoInventarioDetalle.__table__,
            InventarioStock.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def test_compra_genera_ingreso_inventario():
    engine = _build_test_engine()
    service = CompraService()

    with Session(engine) as session:
        tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
        session.add(tipo)

        empresa = Empresa(
            razon_social="Empresa Compras",
            nombre_comercial="Empresa Compras",
            ruc="1790012345001",
            direccion_matriz="Av. Central",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(empresa)
        session.flush()

        bodega = Bodega(
            codigo_bodega="BOD-CMP-001",
            nombre_bodega="Bodega Compras",
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(bodega)

        producto = Producto(
            nombre="Producto Compra Orq",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(producto)
        session.flush()

        stock = InventarioStock(
            bodega_id=bodega.id,
            producto_id=producto.id,
            cantidad_actual=Decimal("10.0000"),
            costo_promedio_vigente=Decimal("10.0000"),
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(stock)
        session.commit()

        compra = service.registrar_compra(
            session,
            CompraCreate(
                proveedor_id=empresa.id,
                secuencial_factura="001-001-123456789",
                autorizacion_sri="1" * 49,
                fecha_emision=date.today(),
                bodega_id=bodega.id,
                sustento_tributario="01",
                tipo_identificacion_proveedor="RUC",
                identificacion_proveedor="1790099988001",
                forma_pago="TRANSFERENCIA",
                usuario_auditoria="compras.user",
                detalles=[
                    VentaCompraDetalleCreate(
                        producto_id=producto.id,
                        descripcion="Ingreso compra",
                        cantidad=Decimal("10.0000"),
                        precio_unitario=Decimal("20.0000"),
                        descuento=Decimal("0.00"),
                        impuestos=[
                            ImpuestoAplicadoInput(
                                tipo_impuesto=TipoImpuestoMVP.IVA,
                                codigo_impuesto_sri="2",
                                codigo_porcentaje_sri="0",
                                tarifa=Decimal("0.00"),
                            )
                        ],
                    )
                ],
            ),
        )

        movimiento = session.exec(
            select(MovimientoInventario).where(
                MovimientoInventario.referencia_documento == f"COMPRA:{compra.id}",
                MovimientoInventario.tipo_movimiento == TipoMovimientoInventario.INGRESO,
            )
        ).first()
        assert movimiento is not None
        assert movimiento.estado == EstadoMovimientoInventario.CONFIRMADO

        stock_actual = session.exec(
            select(InventarioStock).where(
                InventarioStock.bodega_id == bodega.id,
                InventarioStock.producto_id == producto.id,
            )
        ).one()
        assert stock_actual.cantidad_actual == Decimal("20.0000")
        assert stock_actual.costo_promedio_vigente == Decimal("15.0000")
        session.refresh(producto)
        assert producto.cantidad == 20


def test_compra_registrada_no_permite_edicion():
    engine = _build_test_engine()
    service = CompraService()

    with Session(engine) as session:
        tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
        session.add(tipo)
        empresa = Empresa(
            razon_social="Empresa Compras Edit",
            nombre_comercial="Empresa Compras Edit",
            ruc="1790012345001",
            direccion_matriz="Av. Central",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(empresa)
        session.flush()
        bodega = Bodega(
            codigo_bodega="BOD-CMP-002",
            nombre_bodega="Bodega Compras Edit",
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(bodega)
        producto = Producto(
            nombre="Producto Compra Edit",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(producto)
        session.commit()

        compra = service.registrar_compra(
            session,
            CompraCreate(
                proveedor_id=empresa.id,
                secuencial_factura="001-001-999999999",
                autorizacion_sri="3" * 49,
                fecha_emision=date.today(),
                bodega_id=bodega.id,
                sustento_tributario="01",
                tipo_identificacion_proveedor="RUC",
                identificacion_proveedor="1790099988001",
                forma_pago="EFECTIVO",
                usuario_auditoria="compras.user",
                detalles=[
                    VentaCompraDetalleCreate(
                        producto_id=producto.id,
                        descripcion="Ingreso compra",
                        cantidad=Decimal("1.0000"),
                        precio_unitario=Decimal("5.0000"),
                        descuento=Decimal("0.00"),
                        impuestos=[],
                    )
                ],
            ),
        )

        with pytest.raises(HTTPException) as exc:
            service.actualizar_compra(
                session,
                compra.id,
                CompraUpdate(
                    secuencial_factura="001-001-111111111",
                    usuario_auditoria="edit.user",
                ),
            )

        assert exc.value.status_code == 400
        assert "no se puede editar una compra en estado registrada" in exc.value.detail.lower()


def test_registro_compra_inicializa_cxp():
    engine = _build_test_engine()
    service = CompraService()

    with Session(engine) as session:
        tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
        session.add(tipo)
        empresa = Empresa(
            razon_social="Empresa CxP",
            nombre_comercial="Empresa CxP",
            ruc="1790012345001",
            direccion_matriz="Av. Central",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(empresa)
        session.flush()
        bodega = Bodega(
            codigo_bodega="BOD-CXP-001",
            nombre_bodega="Bodega CxP",
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(bodega)
        producto = Producto(
            nombre="Producto CxP",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(producto)
        session.commit()

        compra = service.registrar_compra(
            session,
            CompraCreate(
                proveedor_id=empresa.id,
                secuencial_factura="001-001-222222222",
                autorizacion_sri="4" * 49,
                fecha_emision=date.today(),
                bodega_id=bodega.id,
                sustento_tributario="01",
                tipo_identificacion_proveedor="RUC",
                identificacion_proveedor="1790099988001",
                forma_pago="EFECTIVO",
                usuario_auditoria="compras.user",
                detalles=[
                    VentaCompraDetalleCreate(
                        producto_id=producto.id,
                        descripcion="Compra base CxP",
                        cantidad=Decimal("10.0000"),
                        precio_unitario=Decimal("10.0000"),
                        descuento=Decimal("0.00"),
                        impuestos=[],
                    )
                ],
            ),
        )

        cxp = session.exec(
            select(CuentaPorPagar).where(CuentaPorPagar.compra_id == compra.id)
        ).first()
        assert cxp is not None
        assert cxp.valor_total_factura == Decimal("100.00")
        assert cxp.valor_retenido == Decimal("0.00")
        assert cxp.pagos_acumulados == Decimal("0.00")
        assert cxp.saldo_pendiente == Decimal("100.00")
        assert cxp.estado == EstadoCuentaPorPagar.PENDIENTE


def test_anular_compra_revierte_cantidad_inventario():
    engine = _build_test_engine()
    service = CompraService()
    kardex_service = MovimientoInventarioService()

    with Session(engine) as session:
        tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
        session.add(tipo)
        empresa = Empresa(
            razon_social="Empresa Compra Anulacion",
            nombre_comercial="Empresa Compra Anulacion",
            ruc="1790012345001",
            direccion_matriz="Av. Central",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(empresa)
        session.flush()
        bodega = Bodega(
            codigo_bodega="BOD-ANU-001",
            nombre_bodega="Bodega Compra Anulacion",
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(bodega)
        producto = Producto(
            nombre="Producto Compra Anulacion",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(producto)
        session.flush()

        stock_inicial = InventarioStock(
            bodega_id=bodega.id,
            producto_id=producto.id,
            cantidad_actual=Decimal("0.0000"),
            costo_promedio_vigente=Decimal("0.0000"),
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(stock_inicial)
        session.commit()

        compra = service.registrar_compra(
            session,
            CompraCreate(
                proveedor_id=empresa.id,
                secuencial_factura="001-001-333333333",
                autorizacion_sri="5" * 49,
                fecha_emision=date.today(),
                bodega_id=bodega.id,
                sustento_tributario="01",
                tipo_identificacion_proveedor="RUC",
                identificacion_proveedor="1790099988001",
                forma_pago="EFECTIVO",
                usuario_auditoria="compras.user",
                detalles=[
                    VentaCompraDetalleCreate(
                        producto_id=producto.id,
                        descripcion="Compra para anular",
                        cantidad=Decimal("10.0000"),
                        precio_unitario=Decimal("10.0000"),
                        descuento=Decimal("0.00"),
                        impuestos=[],
                    )
                ],
            ),
        )

        stock_post_compra = session.exec(
            select(InventarioStock).where(
                InventarioStock.bodega_id == bodega.id,
                InventarioStock.producto_id == producto.id,
            )
        ).one()
        assert stock_post_compra.cantidad_actual == Decimal("10.0000")

        compra_anulada = service.anular_compra(
            session,
            compra.id,
            payload=CompraAnularRequest(usuario_auditoria="compras.user"),
        )

        assert compra_anulada.estado == EstadoCompra.ANULADA

        stock_post_anulacion = session.exec(
            select(InventarioStock).where(
                InventarioStock.bodega_id == bodega.id,
                InventarioStock.producto_id == producto.id,
            )
        ).one()
        assert stock_post_anulacion.cantidad_actual == Decimal("0.0000")
        session.refresh(producto)
        assert producto.cantidad == 0

        movimiento_egreso = session.exec(
            select(MovimientoInventario).where(
                MovimientoInventario.referencia_documento == f"ANULACION_COMPRA:{compra.id}",
                MovimientoInventario.tipo_movimiento == TipoMovimientoInventario.EGRESO,
            )
        ).first()
        assert movimiento_egreso is not None
        assert movimiento_egreso.estado == EstadoMovimientoInventario.CONFIRMADO

        kardex = kardex_service.obtener_kardex(
            session,
            producto_id=producto.id,
            bodega_id=bodega.id,
        )
        assert kardex["movimientos"][-1]["saldo_cantidad"] == stock_post_anulacion.cantidad_actual
        assert kardex["movimientos"][-1]["saldo_cantidad"] == Decimal(producto.cantidad).quantize(Decimal("0.0000"))


def test_endpoint_anular_compra_revierte_inventario():
    engine = _build_test_engine()
    service = CompraService()

    with Session(engine) as session:
        tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
        session.add(tipo)
        empresa = Empresa(
            razon_social="Empresa Compra API",
            nombre_comercial="Empresa Compra API",
            ruc="1790012345001",
            direccion_matriz="Av. Central",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(empresa)
        session.flush()
        bodega = Bodega(
            codigo_bodega="BOD-ANU-API",
            nombre_bodega="Bodega Compra API",
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(bodega)
        producto = Producto(
            nombre="Producto Compra API",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(producto)
        session.flush()

        session.add(
            InventarioStock(
                bodega_id=bodega.id,
                producto_id=producto.id,
                cantidad_actual=Decimal("0.0000"),
                costo_promedio_vigente=Decimal("0.0000"),
                usuario_auditoria="seed",
                activo=True,
            )
        )
        session.commit()

        compra = service.registrar_compra(
            session,
            CompraCreate(
                proveedor_id=empresa.id,
                secuencial_factura="001-001-444444444",
                autorizacion_sri="6" * 49,
                fecha_emision=date.today(),
                bodega_id=bodega.id,
                sustento_tributario="01",
                tipo_identificacion_proveedor="RUC",
                identificacion_proveedor="1790099988001",
                forma_pago="EFECTIVO",
                usuario_auditoria="compras.user",
                detalles=[
                    VentaCompraDetalleCreate(
                        producto_id=producto.id,
                        descripcion="Compra endpoint anular",
                        cantidad=Decimal("10.0000"),
                        precio_unitario=Decimal("10.0000"),
                        descuento=Decimal("0.00"),
                        impuestos=[],
                    )
                ],
            ),
        )
        compra_id = compra.id
        bodega_id = bodega.id
        producto_id = producto.id

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/compras/{compra_id}/anular",
                json={"usuario_auditoria": "api.user"},
            )
            assert response.status_code == 200, response.text
            assert response.json()["estado"] == "ANULADA"
    finally:
        app.dependency_overrides.pop(get_session, None)

    with Session(engine) as session:
        stock_final = session.exec(
            select(InventarioStock).where(
                InventarioStock.bodega_id == bodega_id,
                InventarioStock.producto_id == producto_id,
            )
        ).one()
        assert stock_final.cantidad_actual == Decimal("0.0000")
        producto_final = session.get(Producto, producto_id)
        assert producto_final is not None
        assert producto_final.cantidad == 0
