from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.core_sri.models import CuentaPorCobrar, Venta, VentaDetalle, VentaDetalleImpuesto
from osiris.modules.sri.core_sri.types import EstadoVenta
from osiris.modules.sri.core_sri.all_schemas import (
    ImpuestoAplicadoInput,
    VentaCompraDetalleCreate,
    VentaCreate,
)
from osiris.modules.ventas.services.venta_service import VentaService
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.movimientos.models import (
    EstadoMovimientoInventario,
    InventarioStock,
    MovimientoInventario,
    MovimientoInventarioDetalle,
    TipoMovimientoInventario,
)
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
            Venta.__table__,
            VentaDetalle.__table__,
            VentaDetalleImpuesto.__table__,
            CuentaPorCobrar.__table__,
            MovimientoInventario.__table__,
            MovimientoInventarioDetalle.__table__,
            InventarioStock.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def _seed_base(session: Session):
    tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
    session.add(tipo)

    empresa = Empresa(
        razon_social="Empresa Ventas",
        nombre_comercial="Empresa Ventas",
        ruc="1790012345001",
        direccion_matriz="Av. Principal",
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
        codigo_bodega="BOD-VTA-001",
        nombre_bodega="Bodega Ventas",
        empresa_id=empresa.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(bodega)

    producto = Producto(
        nombre="Producto Venta Orq",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        cantidad=0,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(producto)
    session.flush()
    return bodega, producto


def _payload_venta(bodega_id, producto_id, cantidad: Decimal) -> VentaCreate:
    return VentaCreate(
        fecha_emision=date.today(),
        bodega_id=bodega_id,
        tipo_identificacion_comprador="RUC",
        identificacion_comprador="1790012345001",
        forma_pago="EFECTIVO",
        usuario_auditoria="tester",
        detalles=[
            VentaCompraDetalleCreate(
                producto_id=producto_id,
                descripcion="Item venta",
                cantidad=cantidad,
                precio_unitario=Decimal("10.00"),
                descuento=Decimal("0.00"),
                impuestos=[
                    ImpuestoAplicadoInput(
                        tipo_impuesto="IVA",
                        codigo_impuesto_sri="2",
                        codigo_porcentaje_sri="0",
                        tarifa=Decimal("0.00"),
                    )
                ],
            )
        ],
    )


def test_emitir_venta_genera_egreso_automatico():
    engine = _build_test_engine()
    service = VentaService()

    with Session(engine) as session:
        bodega, producto = _seed_base(session)
        stock = InventarioStock(
            bodega_id=bodega.id,
            producto_id=producto.id,
            cantidad_actual=Decimal("20.0000"),
            costo_promedio_vigente=Decimal("5.0000"),
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(stock)
        session.commit()

        venta = service.registrar_venta(
            session,
            _payload_venta(bodega.id, producto.id, Decimal("3.0000")),
        )
        assert venta.estado == EstadoVenta.BORRADOR

        sin_movimiento = session.exec(
            select(MovimientoInventario).where(
                MovimientoInventario.referencia_documento == f"VENTA:{venta.id}",
                MovimientoInventario.tipo_movimiento == TipoMovimientoInventario.EGRESO,
            )
        ).first()
        assert sin_movimiento is None

        venta = service.emitir_venta(
            session,
            venta.id,
            usuario_auditoria="tester",
            encolar_sri=False,
        )
        assert venta.estado == EstadoVenta.EMITIDA

        movimiento = session.exec(
            select(MovimientoInventario).where(
                MovimientoInventario.referencia_documento == f"VENTA:{venta.id}",
                MovimientoInventario.tipo_movimiento == TipoMovimientoInventario.EGRESO,
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
        assert stock_actual.cantidad_actual == Decimal("17.0000")
        session.refresh(producto)
        assert producto.cantidad == 17


def test_emitir_venta_rollback_sin_stock():
    engine = _build_test_engine()
    service = VentaService()

    with Session(engine) as session:
        bodega, producto = _seed_base(session)
        stock = InventarioStock(
            bodega_id=bodega.id,
            producto_id=producto.id,
            cantidad_actual=Decimal("1.0000"),
            costo_promedio_vigente=Decimal("5.0000"),
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(stock)
        session.commit()

        venta = service.registrar_venta(
            session,
            _payload_venta(bodega.id, producto.id, Decimal("5.0000")),
        )
        assert venta.estado == EstadoVenta.BORRADOR

        with pytest.raises(ValueError) as exc:
            service.emitir_venta(
                session,
                venta.id,
                usuario_auditoria="tester",
                encolar_sri=False,
            )

        assert "stock insuficiente" in str(exc.value).lower()

        movimientos = session.exec(
            select(MovimientoInventario).where(
                MovimientoInventario.referencia_documento.like("VENTA:%")
            )
        ).all()
        assert len(movimientos) == 0
