from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.sri.core_sri.models import (
    Compra,
    CuentaPorPagar,
    EstadoCompra,
    EstadoCuentaPorPagar,
    FormaPagoSRI,
    PagoCxP,
    SustentoTributarioSRI,
    TipoIdentificacionSRI,
)


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AuditLog.__table__,
            Compra.__table__,
            CuentaPorPagar.__table__,
            PagoCxP.__table__,
        ],
    )
    return engine


def _crear_compra_y_cxp(session: Session) -> tuple[Compra, CuentaPorPagar]:
    compra = Compra(
        proveedor_id=uuid4(),
        secuencial_factura="001-001-123456789",
        autorizacion_sri="1" * 49,
        fecha_emision=date(2026, 2, 26),
        sustento_tributario=SustentoTributarioSRI.CREDITO_TRIBUTARIO_BIENES,
        tipo_identificacion_proveedor=TipoIdentificacionSRI.RUC,
        identificacion_proveedor="1790012345001",
        forma_pago=FormaPagoSRI.TRANSFERENCIA,
        subtotal_sin_impuestos=Decimal("100.00"),
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("100.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("100.00"),
        estado=EstadoCompra.REGISTRADA,
        usuario_auditoria="test",
        activo=True,
    )
    session.add(compra)
    session.flush()

    cxp = CuentaPorPagar(
        compra_id=compra.id,
        valor_total_factura=Decimal("100.00"),
        valor_retenido=Decimal("0.00"),
        pagos_acumulados=Decimal("0.00"),
        saldo_pendiente=Decimal("100.00"),
        estado=EstadoCuentaPorPagar.PENDIENTE,
        usuario_auditoria="test",
        activo=True,
    )
    session.add(cxp)
    session.commit()
    session.refresh(compra)
    session.refresh(cxp)
    return compra, cxp


def test_cxp_listar_y_obtener_por_compra():
    engine = _build_test_engine()
    with Session(engine) as session:
        compra, _ = _crear_compra_y_cxp(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            listado = client.get("/api/v1/cxp", params={"limit": 10, "offset": 0})
            detalle = client.get(f"/api/v1/cxp/{compra.id}")

        assert listado.status_code == 200, listado.text
        body = listado.json()
        assert body["meta"]["total"] == 1
        assert body["items"][0]["numero_factura"] == "001-001-123456789"
        assert body["items"][0]["saldo_pendiente"] == "100.00"

        assert detalle.status_code == 200, detalle.text
        det = detalle.json()
        assert det["compra_id"] == str(compra.id)
        assert det["estado"] == "PENDIENTE"
        assert det["saldo_pendiente"] == "100.00"
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_cxp_registrar_pago_actualiza_saldo_y_estado():
    engine = _build_test_engine()
    with Session(engine) as session:
        compra, _ = _crear_compra_y_cxp(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/cxp/{compra.id}/pagos",
                json={
                    "monto": "40.00",
                    "fecha": "2026-02-26",
                    "forma_pago": "EFECTIVO",
                    "usuario_auditoria": "tesoreria",
                },
            )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["monto"] == "40.00"
        assert body["forma_pago"] == "EFECTIVO"

        with Session(engine) as session:
            cxp = session.exec(select(CuentaPorPagar).where(CuentaPorPagar.compra_id == compra.id)).one()
            assert cxp.pagos_acumulados == Decimal("40.00")
            assert cxp.saldo_pendiente == Decimal("60.00")
            assert cxp.estado == EstadoCuentaPorPagar.PARCIAL
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_cxp_registrar_pago_rechaza_sobrepago():
    engine = _build_test_engine()
    with Session(engine) as session:
        compra, _ = _crear_compra_y_cxp(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/cxp/{compra.id}/pagos",
                json={
                    "monto": "110.00",
                    "fecha": "2026-02-26",
                    "forma_pago": "TRANSFERENCIA",
                    "usuario_auditoria": "tesoreria",
                },
            )

        assert response.status_code == 400, response.text
        assert "saldo pendiente" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_session, None)
