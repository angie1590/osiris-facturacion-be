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
from osiris.modules.common.empleado.entity import Empleado
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.sri.core_sri.models import (
    DocumentoElectronico,
    EstadoDocumentoElectronico,
    EstadoVenta,
    FormaPagoSRI,
    TipoDocumentoElectronico,
    TipoIdentificacionSRI,
    Venta,
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
            Empresa.__table__,
            Usuario.__table__,
            Empleado.__table__,
            Venta.__table__,
            DocumentoElectronico.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def _seed_documento(session: Session, *, estado: EstadoDocumentoElectronico, xml: str | None) -> tuple[Usuario, DocumentoElectronico]:
    session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
    session.flush()

    empresa = Empresa(
        razon_social="Empresa Docs",
        nombre_comercial="Empresa Docs",
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

    persona_id = uuid4()
    usuario = Usuario(
        persona_id=persona_id,
        rol_id=uuid4(),
        username=f"user.{uuid4().hex[:8]}",
        password_hash="hash",
        requiere_cambio_password=False,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(usuario)
    session.flush()

    empleado = Empleado(
        persona_id=persona_id,
        empresa_id=empresa.id,
        salario=500.00,
        fecha_ingreso=date.today(),
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(empleado)

    venta = Venta(
        empresa_id=empresa.id,
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
        estado=EstadoVenta.EMITIDA,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(venta)
    session.flush()

    documento = DocumentoElectronico(
        tipo_documento=TipoDocumentoElectronico.FACTURA,
        referencia_id=venta.id,
        venta_id=venta.id,
        clave_acceso="1" * 49,
        estado_sri=estado,
        estado=estado,
        xml_autorizado=xml,
        intentos=0,
        next_retry_at=None,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(documento)
    session.commit()
    session.refresh(usuario)
    session.refresh(documento)
    return usuario, documento


def test_descargar_xml_autorizado():
    engine = _build_test_engine()

    with Session(engine) as session:
        usuario, documento = _seed_documento(
            session,
            estado=EstadoDocumentoElectronico.AUTORIZADO,
            xml="<factura>ok</factura>",
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/documentos/{documento.id}/xml",
                headers={"Authorization": f"Bearer {usuario.id}"},
            )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/xml")
        assert "<factura>ok</factura>" in response.text
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_descargar_xml_en_cola_falla():
    engine = _build_test_engine()

    with Session(engine) as session:
        usuario, documento = _seed_documento(
            session,
            estado=EstadoDocumentoElectronico.EN_COLA,
            xml=None,
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/documentos/{documento.id}/xml",
                headers={"Authorization": f"Bearer {usuario.id}"},
            )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.pop(get_session, None)
