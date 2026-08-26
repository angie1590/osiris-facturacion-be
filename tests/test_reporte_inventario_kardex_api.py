from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
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
            Bodega.__table__,
            Producto.__table__,
            MovimientoInventario.__table__,
            MovimientoInventarioDetalle.__table__,
        ],
    )
    return engine


def _seed_contexto(session: Session):
    session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
    session.flush()

    empresa = Empresa(
        razon_social="Empresa Kardex",
        nombre_comercial="Empresa Kardex",
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

    sucursal = Sucursal(
        codigo="001",
        nombre="Sucursal Kardex",
        direccion="Av. 1",
        telefono="022000000",
        es_matriz=True,
        empresa_id=empresa.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(sucursal)
    session.flush()

    bodega = Bodega(
        codigo_bodega="BOD-KDX-1",
        nombre_bodega="Bodega Kardex",
        empresa_id=empresa.id,
        sucursal_id=sucursal.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(bodega)
    session.flush()

    producto = Producto(
        nombre=f"Producto Kardex {str(empresa.id)[:8]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        cantidad=0,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(producto)
    session.commit()
    return bodega.id, producto.id


def _crear_movimiento(
    session: Session,
    *,
    bodega_id,
    producto_id,
    fecha_movimiento: date,
    tipo_movimiento: TipoMovimientoInventario,
    cantidad: Decimal,
    costo_unitario: Decimal,
    referencia_documento: str = "TEST",
):
    movimiento = MovimientoInventario(
        fecha=fecha_movimiento,
        bodega_id=bodega_id,
        tipo_movimiento=tipo_movimiento,
        estado=EstadoMovimientoInventario.CONFIRMADO,
        referencia_documento=referencia_documento,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(movimiento)
    session.flush()
    session.add(
        MovimientoInventarioDetalle(
            movimiento_inventario_id=movimiento.id,
            producto_id=producto_id,
            cantidad=cantidad,
            costo_unitario=costo_unitario,
            usuario_auditoria="seed",
            activo=True,
        )
    )
    session.commit()


def test_kardex_default_dates_calcula_un_anio():
    engine = _build_test_engine()
    with Session(engine) as session:
        bodega_id, producto_id = _seed_contexto(session)
        _crear_movimiento(
            session,
            bodega_id=bodega_id,
            producto_id=producto_id,
            fecha_movimiento=date.today() - timedelta(days=30),
            tipo_movimiento=TipoMovimientoInventario.INGRESO,
            cantidad=Decimal("5.0000"),
            costo_unitario=Decimal("3.0000"),
        )
        _crear_movimiento(
            session,
            bodega_id=bodega_id,
            producto_id=producto_id,
            fecha_movimiento=date.today() - timedelta(days=400),
            tipo_movimiento=TipoMovimientoInventario.INGRESO,
            cantidad=Decimal("9.0000"),
            costo_unitario=Decimal("3.0000"),
        )

    tracked_statements = []

    class TrackingSession(Session):
        def exec(self, statement, *args, **kwargs):
            tracked_statements.append(statement)
            return super().exec(statement, *args, **kwargs)

    def override_get_session():
        with TrackingSession(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/reportes/inventario/kardex/{producto_id}")

        assert response.status_code == 200, response.text
        data = response.json()

        expected_inicio = date.today() - timedelta(days=365)
        expected_fin = date.today()
        assert data["fecha_inicio"] == expected_inicio.isoformat()
        assert data["fecha_fin"] == expected_fin.isoformat()
        assert len(data["movimientos"]) == 1
        assert data["movimientos"][0]["fecha"] == (date.today() - timedelta(days=30)).isoformat()

        kardex_stmt = next(
            stmt
            for stmt in tracked_statements
            if "tbl_movimiento_inventario_detalle.producto_id" in str(stmt)
            and "tbl_movimiento_inventario.fecha >=" in str(stmt)
            and "tbl_movimiento_inventario.fecha <=" in str(stmt)
        )
        compiled_params = kardex_stmt.compile().params
        assert expected_inicio in compiled_params.values()
        assert expected_fin in compiled_params.values()
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_kardex_calculo_saldo_cronologico():
    engine = _build_test_engine()
    with Session(engine) as session:
        bodega_id, producto_id = _seed_contexto(session)
        _crear_movimiento(
            session,
            bodega_id=bodega_id,
            producto_id=producto_id,
            fecha_movimiento=date(2026, 2, 1),
            tipo_movimiento=TipoMovimientoInventario.INGRESO,
            cantidad=Decimal("10.0000"),
            costo_unitario=Decimal("5.0000"),
        )
        _crear_movimiento(
            session,
            bodega_id=bodega_id,
            producto_id=producto_id,
            fecha_movimiento=date(2026, 2, 2),
            tipo_movimiento=TipoMovimientoInventario.EGRESO,
            cantidad=Decimal("2.0000"),
            costo_unitario=Decimal("5.0000"),
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/reportes/inventario/kardex/{producto_id}",
                params={"fecha_inicio": "2026-02-01", "fecha_fin": "2026-02-10"},
            )

        assert response.status_code == 200, response.text
        data = response.json()
        movimientos = data["movimientos"]
        assert [mov["fecha"] for mov in movimientos] == ["2026-02-01", "2026-02-02"]
        assert movimientos[0]["tipo_movimiento"] == "INGRESO"
        assert movimientos[1]["tipo_movimiento"] == "EGRESO"
        assert Decimal(str(movimientos[0]["saldo_cantidad"])) == Decimal("10.0000")
        assert Decimal(str(movimientos[1]["saldo_cantidad"])) == Decimal("8.0000")
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_kardex_filtra_por_sucursal_y_expone_venta():
    engine = _build_test_engine()
    with Session(engine) as session:
        bodega_a_id, producto_id = _seed_contexto(session)
        bodega_a = session.get(Bodega, bodega_a_id)
        assert bodega_a is not None
        sucursal_a_id = bodega_a.sucursal_id
        assert sucursal_a_id is not None

        sucursal_b = Sucursal(
            codigo="002",
            nombre="Sucursal B",
            direccion="Av. 2",
            telefono="022000001",
            es_matriz=False,
            empresa_id=bodega_a.empresa_id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(sucursal_b)
        session.flush()

        bodega_b = Bodega(
            codigo_bodega="BOD-KDX-2",
            nombre_bodega="Bodega Kardex B",
            empresa_id=bodega_a.empresa_id,
            sucursal_id=sucursal_b.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(bodega_b)
        session.commit()

        _crear_movimiento(
            session,
            bodega_id=bodega_a_id,
            producto_id=producto_id,
            fecha_movimiento=date(2026, 2, 1),
            tipo_movimiento=TipoMovimientoInventario.INGRESO,
            cantidad=Decimal("10.0000"),
            costo_unitario=Decimal("5.0000"),
        )
        _crear_movimiento(
            session,
            bodega_id=bodega_a_id,
            producto_id=producto_id,
            fecha_movimiento=date(2026, 2, 2),
            tipo_movimiento=TipoMovimientoInventario.EGRESO,
            cantidad=Decimal("2.0000"),
            costo_unitario=Decimal("5.0000"),
            referencia_documento="VENTA:ABC",
        )
        _crear_movimiento(
            session,
            bodega_id=bodega_b.id,
            producto_id=producto_id,
            fecha_movimiento=date(2026, 2, 3),
            tipo_movimiento=TipoMovimientoInventario.INGRESO,
            cantidad=Decimal("99.0000"),
            costo_unitario=Decimal("1.0000"),
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/reportes/inventario/kardex/{producto_id}",
                params={
                    "fecha_inicio": "2026-02-01",
                    "fecha_fin": "2026-02-10",
                    "sucursal_id": str(sucursal_a_id),
                },
            )

        assert response.status_code == 200, response.text
        data = response.json()
        movimientos = data["movimientos"]
        assert len(movimientos) == 2
        assert [mov["tipo_movimiento"] for mov in movimientos] == ["INGRESO", "VENTA"]
        assert Decimal(str(movimientos[-1]["saldo_cantidad"])) == Decimal("8.0000")
    finally:
        app.dependency_overrides.pop(get_session, None)
