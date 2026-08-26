from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.persona.entity import Persona, TipoIdentificacion
from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad
from osiris.modules.compras.models import Compra
from osiris.modules.sri.core_sri.types import (
    EstadoCompra,
    FormaPagoSRI,
    SustentoTributarioSRI,
    TipoIdentificacionSRI,
)
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
            Persona.__table__,
            ProveedorSociedad.__table__,
            Compra.__table__,
        ],
    )
    return engine


def _crear_proveedor_sociedad(session: Session, *, razon_social: str, ruc: str) -> ProveedorSociedad:
    persona = Persona(
        tipo_identificacion=TipoIdentificacion.CEDULA,
        identificacion=f"{ruc[3:13]}",
        nombre=f"Contacto {razon_social}",
        apellido="Proveedor",
        direccion="Av. Contacto",
        telefono="022000000",
        ciudad="Quito",
        email=f"{ruc}@mail.test",
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(persona)
    session.flush()

    proveedor = ProveedorSociedad(
        ruc=ruc,
        razon_social=razon_social,
        nombre_comercial=razon_social,
        direccion="Av. Proveedor",
        telefono="022111111",
        email=f"{ruc}@proveedor.test",
        tipo_contribuyente_id="01",
        persona_contacto_id=persona.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(proveedor)
    session.flush()
    return proveedor


def _crear_compra(
    session: Session,
    *,
    proveedor_id,
    total: Decimal,
    estado: EstadoCompra = EstadoCompra.REGISTRADA,
):
    session.add(
        Compra(
            proveedor_id=proveedor_id,
            secuencial_factura="001-001-000000001",
            autorizacion_sri="1234567890123456789012345678901234567",
            fecha_emision=date(2026, 2, 20),
            sustento_tributario=SustentoTributarioSRI.CREDITO_TRIBUTARIO_BIENES,
            tipo_identificacion_proveedor=TipoIdentificacionSRI.RUC,
            identificacion_proveedor="1790012345001",
            forma_pago=FormaPagoSRI.TRANSFERENCIA,
            subtotal_sin_impuestos=total,
            subtotal_12=total,
            subtotal_15=Decimal("0.00"),
            subtotal_0=Decimal("0.00"),
            subtotal_no_objeto=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            monto_ice=Decimal("0.00"),
            valor_total=total,
            estado=estado,
            usuario_auditoria="seed",
            activo=True,
        )
    )


def test_compras_proveedor_orden_descendente():
    engine = _build_test_engine()
    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        session.flush()

        proveedor_x = _crear_proveedor_sociedad(
            session,
            razon_social="Proveedor X",
            ruc="1790012345001",
        )
        proveedor_y = _crear_proveedor_sociedad(
            session,
            razon_social="Proveedor Y",
            ruc="1790012345002",
        )
        proveedor_x_id = proveedor_x.id
        proveedor_y_id = proveedor_y.id

        _crear_compra(session, proveedor_id=proveedor_x_id, total=Decimal("50.00"))
        _crear_compra(session, proveedor_id=proveedor_y_id, total=Decimal("200.00"))
        _crear_compra(
            session,
            proveedor_id=proveedor_y_id,
            total=Decimal("999.00"),
            estado=EstadoCompra.ANULADA,
        )
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/reportes/compras/por-proveedor",
                params={
                    "fecha_inicio": "2026-02-01",
                    "fecha_fin": "2026-02-28",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data) == 2
        assert data[0]["proveedor_id"] == str(proveedor_y_id)
        assert data[0]["razon_social"] == "Proveedor Y"
        assert Decimal(str(data[0]["total_compras"])) == Decimal("200.00")
        assert int(data[0]["cantidad_facturas"]) == 1
        assert data[1]["proveedor_id"] == str(proveedor_x_id)
        assert Decimal(str(data[1]["total_compras"])) == Decimal("50.00")
    finally:
        app.dependency_overrides.pop(get_session, None)
