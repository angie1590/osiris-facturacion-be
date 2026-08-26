from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.core_sri.models import (
    EstadoVenta,
    FormaPagoSRI,
    TipoIdentificacionSRI,
    Venta,
    VentaDetalle,
)
from osiris.modules.inventario.movimientos.models import (
    EstadoMovimientoInventario,
    MovimientoInventario,
    MovimientoInventarioDetalle,
    TipoMovimientoInventario,
)
from osiris.modules.inventario.bodega.entity import Bodega
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
            AuditLog.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            PuntoEmision.__table__,
            Bodega.__table__,
            Producto.__table__,
            Venta.__table__,
            VentaDetalle.__table__,
            MovimientoInventario.__table__,
            MovimientoInventarioDetalle.__table__,
        ],
    )
    return engine


def _seed_contexto(session: Session):
    session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
    session.flush()

    empresa = Empresa(
        razon_social="Empresa Rentabilidad",
        nombre_comercial="Empresa Rentabilidad",
        ruc="1790012345001",
        direccion_matriz="Av. Matriz",
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

    sucursal = Sucursal(
        codigo="001",
        nombre="Sucursal Matriz",
        direccion="Av. 1",
        telefono="022000000",
        es_matriz=True,
        empresa_id=empresa.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(sucursal)
    session.flush()

    punto_emision = PuntoEmision(
        codigo="001",
        descripcion="Punto Matriz",
        secuencial_actual=1,
        sucursal_id=sucursal.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(punto_emision)

    bodega = Bodega(
        codigo_bodega="BOD-REN-001",
        nombre_bodega="Bodega Rentabilidad",
        empresa_id=empresa.id,
        sucursal_id=sucursal.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(bodega)

    producto = Producto(
        nombre=f"Producto Rentabilidad {str(empresa.id)[:8]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("100.00"),
        cantidad=0,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(producto)
    session.commit()
    return empresa.id, punto_emision.id, bodega.id, producto.id


def _crear_venta_con_costo_historico(
    session: Session,
    *,
    empresa_id,
    punto_emision_id,
    bodega_id,
    producto_id,
    cliente_id,
    subtotal: Decimal,
    costo_historico: Decimal,
    fecha_emision: date,
) -> Venta:
    venta = Venta(
        cliente_id=cliente_id,
        empresa_id=empresa_id,
        punto_emision_id=punto_emision_id,
        fecha_emision=fecha_emision,
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador="1790012345001",
        forma_pago=FormaPagoSRI.EFECTIVO,
        subtotal_sin_impuestos=subtotal,
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=subtotal,
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=subtotal,
        estado=EstadoVenta.EMITIDA,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(venta)
    session.flush()

    session.add(
        VentaDetalle(
            venta_id=venta.id,
            producto_id=producto_id,
            descripcion="Detalle rentabilidad",
            cantidad=Decimal("1.0000"),
            precio_unitario=subtotal,
            descuento=Decimal("0.00"),
            subtotal_sin_impuesto=subtotal,
            usuario_auditoria="seed",
            activo=True,
        )
    )
    session.flush()

    mov = MovimientoInventario(
        fecha=fecha_emision,
        bodega_id=bodega_id,
        tipo_movimiento=TipoMovimientoInventario.EGRESO,
        estado=EstadoMovimientoInventario.CONFIRMADO,
        referencia_documento=f"VENTA:{venta.id}",
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(mov)
    session.flush()
    session.add(
        MovimientoInventarioDetalle(
            movimiento_inventario_id=mov.id,
            producto_id=producto_id,
            cantidad=Decimal("1.0000"),
            costo_unitario=costo_historico,
            usuario_auditoria="seed",
            activo=True,
        )
    )
    session.commit()
    session.refresh(venta)
    return venta


def test_rentabilidad_cliente_margen_correcto():
    engine = _build_test_engine()
    cliente_id = uuid4()
    with Session(engine) as session:
        empresa_id, punto_emision_id, bodega_id, producto_id = _seed_contexto(session)
        _crear_venta_con_costo_historico(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            bodega_id=bodega_id,
            producto_id=producto_id,
            cliente_id=cliente_id,
            subtotal=Decimal("100.00"),
            costo_historico=Decimal("60.00"),
            fecha_emision=date(2026, 2, 20),
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/reportes/rentabilidad/por-cliente",
                params={"fecha_inicio": "2026-02-01", "fecha_fin": "2026-02-28"},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data) == 1
        assert data[0]["cliente_id"] == str(cliente_id)
        assert Decimal(str(data[0]["utilidad_bruta_dolares"])) == Decimal("40.00")
        assert Decimal(str(data[0]["margen_porcentual"])) == Decimal("40.00")
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_utilidad_transaccional_detecta_perdida():
    engine = _build_test_engine()
    with Session(engine) as session:
        empresa_id, punto_emision_id, bodega_id, producto_id = _seed_contexto(session)
        venta = _crear_venta_con_costo_historico(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            bodega_id=bodega_id,
            producto_id=producto_id,
            cliente_id=uuid4(),
            subtotal=Decimal("100.00"),
            costo_historico=Decimal("120.00"),
            fecha_emision=date(2026, 2, 21),
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/reportes/rentabilidad/transacciones",
                params={"fecha_inicio": "2026-02-01", "fecha_fin": "2026-02-28"},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data) == 1
        assert data[0]["venta_id"] == str(venta.id)
        assert Decimal(str(data[0]["utilidad_bruta_dolares"])) == Decimal("-20.00")
        assert Decimal(str(data[0]["margen_porcentual"])) < Decimal("0.00")
    finally:
        app.dependency_overrides.pop(get_session, None)
