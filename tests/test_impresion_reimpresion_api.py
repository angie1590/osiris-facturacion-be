from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.persona.entity import Persona, TipoIdentificacion
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.sri.core_sri.types import (
    EstadoDocumentoElectronico,
    EstadoVenta,
    FormaPagoSRI,
    TipoDocumentoElectronico,
    TipoIdentificacionSRI,
)
from osiris.modules.sri.facturacion_electronica.models import DocumentoElectronico
from osiris.modules.ventas.models import CuentaPorCobrar, PagoCxC, Venta
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
            Persona.__table__,
            Rol.__table__,
            Usuario.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            PuntoEmision.__table__,
            Venta.__table__,
            CuentaPorCobrar.__table__,
            PagoCxC.__table__,
            DocumentoElectronico.__table__,
        ],
    )
    return engine


def test_reimpresion_incrementa_contador_y_audita():
    engine = _build_test_engine()
    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        session.flush()

        persona = Persona(
            tipo_identificacion=TipoIdentificacion.CEDULA,
            identificacion="0102030405",
            nombre="Caja",
            apellido="User",
            email="cajero@test.local",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(persona)
        session.flush()

        rol = Rol(
            nombre="CAJERO",
            descripcion="Rol cajero",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(rol)
        session.flush()

        usuario = Usuario(
            persona_id=persona.id,
            rol_id=rol.id,
            username="cajero_test",
            password_hash="hash",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(usuario)
        session.flush()

        empresa = Empresa(
            razon_social="Empresa Reimpresion",
            nombre_comercial="Empresa Reimpresion",
            ruc="1790012345001",
            direccion_matriz="Av. Matriz",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(empresa)
        session.flush()

        sucursal = Sucursal(
            codigo="001",
            nombre="Matriz",
            direccion="Av. 1",
            telefono="022000000",
            es_matriz=True,
            empresa_id=empresa.id,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(sucursal)
        session.flush()

        punto = PuntoEmision(
            codigo="001",
            descripcion="Punto Matriz",
            secuencial_actual=1,
            sucursal_id=sucursal.id,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(punto)
        session.flush()

        venta = Venta(
            empresa_id=empresa.id,
            punto_emision_id=punto.id,
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
            cantidad_impresiones=1,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(venta)
        session.flush()

        documento = DocumentoElectronico(
            tipo_documento=TipoDocumentoElectronico.FACTURA,
            referencia_id=venta.id,
            venta_id=venta.id,
            clave_acceso="1234567890123456789012345678901234567890123456789",
            estado_sri=EstadoDocumentoElectronico.AUTORIZADO,
            estado=EstadoDocumentoElectronico.AUTORIZADO,
            cantidad_impresiones=1,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(documento)
        session.commit()
        documento_id = documento.id
        venta_id = venta.id
        usuario_id = usuario.id

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/impresion/documento/{documento_id}/reimprimir",
                json={"motivo": "Se atasco el papel", "formato": "TICKET_80MM"},
                headers={"X-User-Id": str(usuario_id)},
            )

        assert response.status_code == 200, response.text

        with Session(engine) as session:
            documento_actualizado = session.get(DocumentoElectronico, documento_id)
            assert documento_actualizado is not None
            assert documento_actualizado.cantidad_impresiones == 2

            venta_actualizada = session.get(Venta, venta_id)
            assert venta_actualizada is not None
            assert venta_actualizada.cantidad_impresiones == 2

            audit = session.exec(
                select(AuditLog).where(
                    AuditLog.accion == "REIMPRESION_DOCUMENTO",
                    AuditLog.registro_id == str(documento_id),
                )
            ).first()
            assert audit is not None
            assert audit.usuario_id == str(usuario_id)
            assert audit.estado_nuevo.get("motivo") == "Se atasco el papel"
    finally:
        app.dependency_overrides.pop(get_session, None)
