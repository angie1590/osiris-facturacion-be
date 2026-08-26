from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.sri.core_sri.models import FormaPagoSRI, TipoIdentificacionSRI, Venta
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.producto.entity import Producto, TipoProducto


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            CasaComercial.__table__,
            Producto.__table__,
            Venta.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def test_audit_log_creation_on_update():
    engine = _build_test_engine()

    with Session(engine) as session:
        producto = Producto(
            nombre=f"Producto-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(producto)
        session.commit()
        session.refresh(producto)

        producto.pvp = Decimal("12.50")
        session.add(producto)
        session.commit()

        stmt = (
            select(AuditLog)
            .where(
                AuditLog.tabla_afectada == "tbl_producto",
                AuditLog.registro_id == str(producto.id),
                AuditLog.accion == "UPDATE",
            )
            .order_by(AuditLog.fecha.desc())
        )
        log = session.exec(stmt).first()

        assert log is not None
        assert log.estado_anterior["pvp"] == "10.00"
        assert log.estado_nuevo["pvp"] == "12.50"


def test_audit_log_anulation():
    engine = _build_test_engine()

    with Session(engine) as session:
        venta = Venta(
            fecha_emision=date.today(),
            tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
            identificacion_comprador="1790012345001",
            forma_pago=FormaPagoSRI.EFECTIVO,
            subtotal_sin_impuestos=Decimal("100.00"),
            subtotal_12=Decimal("0.00"),
            subtotal_15=Decimal("0.00"),
            subtotal_0=Decimal("100.00"),
            subtotal_no_objeto=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            monto_ice=Decimal("0.00"),
            valor_total=Decimal("100.00"),
            usuario_auditoria="contabilidad",
            activo=True,
        )
        session.add(venta)
        session.commit()
        session.refresh(venta)

        venta.activo = False
        session.add(venta)
        session.commit()

        stmt = (
            select(AuditLog)
            .where(
                AuditLog.tabla_afectada == "tbl_venta",
                AuditLog.registro_id == str(venta.id),
                AuditLog.accion == "ANULAR",
            )
            .order_by(AuditLog.fecha.desc())
        )
        log = session.exec(stmt).first()

        assert log is not None
        assert log.estado_anterior["activo"] is True
        assert log.estado_nuevo["activo"] is False


def test_audit_log_filters():
    engine = _build_test_engine()

    base_time = datetime.utcnow().replace(microsecond=0)
    with Session(engine) as session:
        registros = [
            AuditLog(
                tabla_afectada="tbl_producto",
                registro_id=str(uuid4()),
                entidad="tbl_producto",
                entidad_id=uuid4(),
                accion="UPDATE",
                estado_anterior={"pvp": "10.00"},
                estado_nuevo={"pvp": "12.00"},
                usuario_id="u-1",
                usuario_auditoria="u-1",
                fecha=base_time - timedelta(days=2),
            ),
            AuditLog(
                tabla_afectada="tbl_producto",
                registro_id=str(uuid4()),
                entidad="tbl_producto",
                entidad_id=uuid4(),
                accion="UPDATE",
                estado_anterior={"pvp": "12.00"},
                estado_nuevo={"pvp": "15.00"},
                usuario_id="u-1",
                usuario_auditoria="u-1",
                fecha=base_time - timedelta(hours=12),
            ),
            AuditLog(
                tabla_afectada="tbl_venta",
                registro_id=str(uuid4()),
                entidad="tbl_venta",
                entidad_id=uuid4(),
                accion="ANULAR",
                estado_anterior={"activo": True},
                estado_nuevo={"activo": False},
                usuario_id="u-2",
                usuario_auditoria="u-2",
                fecha=base_time - timedelta(hours=10),
            ),
        ]
        session.add_all(registros)
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            fecha_desde = (base_time - timedelta(days=1)).isoformat()
            fecha_hasta = (base_time - timedelta(hours=1)).isoformat()
            response = client.get(
                "/api/v1/audit-logs",
                params={
                    "usuario_id": "u-1",
                    "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta,
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["usuario_id"] == "u-1"
        assert data[0]["estado_anterior"]["pvp"] == "12.00"
        assert data[0]["estado_nuevo"]["pvp"] == "15.00"
    finally:
        app.dependency_overrides.pop(get_session, None)
