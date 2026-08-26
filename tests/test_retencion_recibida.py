from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.sri.core_sri.models import (
    FormaPagoSRI,
    RetencionRecibida,
    RetencionRecibidaDetalle,
    TipoIdentificacionSRI,
    Venta,
)
from osiris.modules.sri.core_sri.all_schemas import (
    RetencionRecibidaCreate,
    RetencionRecibidaDetalleCreate,
)
from osiris.modules.ventas.services.retencion_recibida_service import RetencionRecibidaService


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
            Venta.__table__,
            RetencionRecibida.__table__,
            RetencionRecibidaDetalle.__table__,
        ],
    )
    return engine


def _crear_venta(
    session: Session,
    *,
    subtotal_sin_impuestos: Decimal = Decimal("100.00"),
    subtotal_12: Decimal = Decimal("100.00"),
    subtotal_15: Decimal = Decimal("0.00"),
    subtotal_0: Decimal = Decimal("0.00"),
    subtotal_no_objeto: Decimal = Decimal("0.00"),
    monto_iva: Decimal = Decimal("12.00"),
    monto_ice: Decimal = Decimal("0.00"),
    valor_total: Decimal = Decimal("112.00"),
) -> Venta:
    venta = Venta(
        fecha_emision=date.today(),
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador="1790012345001",
        forma_pago=FormaPagoSRI.EFECTIVO,
        subtotal_sin_impuestos=subtotal_sin_impuestos,
        subtotal_12=subtotal_12,
        subtotal_15=subtotal_15,
        subtotal_0=subtotal_0,
        subtotal_no_objeto=subtotal_no_objeto,
        monto_iva=monto_iva,
        monto_ice=monto_ice,
        valor_total=valor_total,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(venta)
    session.commit()
    session.refresh(venta)
    return venta


def test_crear_retencion_borrador_exitosa():
    engine = _build_test_engine()
    service = RetencionRecibidaService()

    with Session(engine) as session:
        venta = _crear_venta(session)
        cliente_id = uuid4()
        out = service.crear_retencion_recibida(
            session,
            RetencionRecibidaCreate(
                venta_id=venta.id,
                cliente_id=cliente_id,
                numero_retencion="001-001-123456789",
                fecha_emision=date.today(),
                usuario_auditoria="cobranza.user",
                detalles=[
                    RetencionRecibidaDetalleCreate(
                        codigo_impuesto_sri="1",
                        porcentaje_aplicado=Decimal("1.00"),
                        base_imponible=Decimal("100.00"),
                        valor_retenido=Decimal("1.00"),
                    ),
                    RetencionRecibidaDetalleCreate(
                        codigo_impuesto_sri="2",
                        porcentaje_aplicado=Decimal("30.00"),
                        base_imponible=Decimal("12.00"),
                        valor_retenido=Decimal("3.60"),
                    ),
                ],
            ),
        )

        assert out.estado == "BORRADOR"
        assert out.total_retenido == Decimal("4.60")
        assert len(out.detalles) == 2


def test_validacion_formato_numero_retencion():
    client = TestClient(app)
    payload = {
        "venta_id": "11111111-1111-1111-1111-111111111111",
        "cliente_id": "22222222-2222-2222-2222-222222222222",
        "numero_retencion": "123-45",
        "fecha_emision": "2026-02-20",
        "usuario_auditoria": "cobranza.user",
        "detalles": [
            {
                "codigo_impuesto_sri": "1",
                "porcentaje_aplicado": "1.00",
                "base_imponible": "100.00",
                "valor_retenido": "1.00",
            }
        ],
    }

    response = client.post("/api/v1/retenciones-recibidas", json=payload)
    assert response.status_code == 422


def test_unicidad_retencion_cliente():
    engine = _build_test_engine()
    service = RetencionRecibidaService()

    with Session(engine) as session:
        venta = _crear_venta(session)
        cliente_id = uuid4()
        payload = RetencionRecibidaCreate(
            venta_id=venta.id,
            cliente_id=cliente_id,
            numero_retencion="001-001-555555555",
            fecha_emision=date.today(),
            usuario_auditoria="cobranza.user",
            detalles=[
                RetencionRecibidaDetalleCreate(
                    codigo_impuesto_sri="1",
                    porcentaje_aplicado=Decimal("1.00"),
                    base_imponible=Decimal("100.00"),
                    valor_retenido=Decimal("1.00"),
                )
            ],
        )
        service.crear_retencion_recibida(session, payload)

        with pytest.raises(HTTPException) as exc:
            service.crear_retencion_recibida(session, payload)
        assert exc.value.status_code == 400
        assert "ya existe una retencion recibida" in exc.value.detail.lower()


def test_retencion_recibida_iva_base_incorrecta():
    engine = _build_test_engine()
    service = RetencionRecibidaService()

    with Session(engine) as session:
        venta = _crear_venta(session, monto_iva=Decimal("12.00"), valor_total=Decimal("112.00"))
        with pytest.raises(HTTPException) as exc:
            service.crear_retencion_recibida(
                session,
                RetencionRecibidaCreate(
                    venta_id=venta.id,
                    cliente_id=uuid4(),
                    numero_retencion="001-001-999999991",
                    fecha_emision=date.today(),
                    usuario_auditoria="cobranza.user",
                    detalles=[
                        RetencionRecibidaDetalleCreate(
                            codigo_impuesto_sri="2",
                            porcentaje_aplicado=Decimal("30.00"),
                            base_imponible=Decimal("100.00"),
                            valor_retenido=Decimal("30.00"),
                        )
                    ],
                ),
            )
        assert exc.value.status_code == 400
        assert "base imponible de retencion iva" in str(exc.value.detail).lower()


def test_retencion_recibida_iva_factura_cero():
    engine = _build_test_engine()
    with Session(engine) as session:
        venta = _crear_venta(
            session,
            subtotal_sin_impuestos=Decimal("100.00"),
            subtotal_12=Decimal("0.00"),
            subtotal_0=Decimal("100.00"),
            monto_iva=Decimal("0.00"),
            valor_total=Decimal("100.00"),
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        client = TestClient(app)
        payload = {
            "venta_id": str(venta.id),
            "cliente_id": str(uuid4()),
            "numero_retencion": "001-001-999999992",
            "fecha_emision": str(date.today()),
            "usuario_auditoria": "cobranza.user",
            "detalles": [
                {
                    "codigo_impuesto_sri": "2",
                    "porcentaje_aplicado": "30.00",
                    "base_imponible": "0.00",
                    "valor_retenido": "0.00",
                }
            ],
        }

        response = client.post("/api/v1/retenciones-recibidas", json=payload)
        assert response.status_code == 400
        assert "es ilegal registrar una retencion de iva" in str(response.json()).lower()
    finally:
        app.dependency_overrides.pop(get_session, None)
