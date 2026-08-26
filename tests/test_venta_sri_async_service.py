from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa, RegimenTributario
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.core_sri.models import (
    DocumentoElectronico,
    DocumentoElectronicoHistorial,
    DocumentoSriCola,
    EstadoColaSri,
    EstadoDocumentoElectronico,
    EstadoSriDocumento,
    EstadoVenta,
    FormaPagoSRI,
    TipoIdentificacionSRI,
    TipoImpuestoMVP,
    TipoEmisionVenta,
    Venta,
    VentaDetalle,
    VentaDetalleImpuesto,
)
from osiris.modules.sri.facturacion_electronica.services.venta_sri_async_service import VentaSriAsyncService
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
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
            PuntoEmision.__table__,
            CasaComercial.__table__,
            Producto.__table__,
            Venta.__table__,
            VentaDetalle.__table__,
            VentaDetalleImpuesto.__table__,
            DocumentoElectronico.__table__,
            DocumentoElectronicoHistorial.__table__,
            DocumentoSriCola.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def _crear_venta_electronica(session: Session) -> Venta:
    tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
    session.add(tipo)
    session.flush()

    empresa = Empresa(
        razon_social="Empresa SRI Venta",
        nombre_comercial="Empresa SRI Venta",
        ruc="1790012345001",
        direccion_matriz="Av. Principal",
        telefono="022345678",
        obligado_contabilidad=True,
        regimen=RegimenTributario.GENERAL,
        modo_emision="ELECTRONICO",
        tipo_contribuyente_id="01",
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(empresa)
    session.flush()

    producto = Producto(
        nombre=f"Producto-SRI-{uuid4().hex[:8]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("100.00"),
        cantidad=0,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(producto)
    session.flush()

    venta = Venta(
        empresa_id=empresa.id,
        secuencial_formateado="001-001-000000123",
        fecha_emision=date.today(),
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador="1790012345001",
        forma_pago=FormaPagoSRI.EFECTIVO,
        tipo_emision=TipoEmisionVenta.ELECTRONICA,
        subtotal_sin_impuestos=Decimal("100.00"),
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("100.00"),
        subtotal_0=Decimal("0.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("15.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("115.00"),
        estado=EstadoVenta.EMITIDA,
        estado_sri=EstadoSriDocumento.PENDIENTE,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(venta)
    session.flush()

    detalle = VentaDetalle(
        venta_id=venta.id,
        producto_id=producto.id,
        descripcion="Servicio gravado",
        cantidad=Decimal("1"),
        precio_unitario=Decimal("100.0000"),
        descuento=Decimal("0.00"),
        subtotal_sin_impuesto=Decimal("100.00"),
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(detalle)
    session.flush()

    session.add(
        VentaDetalleImpuesto(
            venta_detalle_id=detalle.id,
            tipo_impuesto=TipoImpuestoMVP.IVA,
            codigo_impuesto_sri="2",
            codigo_porcentaje_sri="4",
            tarifa=Decimal("15.0000"),
            base_imponible=Decimal("100.00"),
            valor_impuesto=Decimal("15.00"),
            usuario_auditoria="seed",
            activo=True,
        )
    )
    session.commit()
    session.refresh(venta)
    return venta


def test_worker_sri_rechazo_definitivo():
    engine = _build_test_engine()

    class GatewayRechazado:
        def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
            _ = (tipo_documento, payload)
            return {"estado": "RECHAZADO", "mensaje": "Clave de acceso duplicada"}

    service = VentaSriAsyncService(gateway=GatewayRechazado(), db_engine=engine)

    with Session(engine) as session:
        venta = _crear_venta_electronica(session)
        tarea = service.encolar_venta(
            session,
            venta_id=venta.id,
            usuario_id="sri-bot",
            commit=True,
        )
        tarea_id = tarea.id
        venta_id = venta.id

    reintentos: list[tuple[str, int]] = []
    correos: list[str] = []
    service.procesar_documento_sri(
        tarea_id,
        scheduler=lambda task_id, delay: reintentos.append((str(task_id), delay)),
        email_dispatcher=lambda v_id: correos.append(str(v_id)),
    )

    with Session(engine) as session:
        venta = session.get(Venta, venta_id)
        tarea = session.get(DocumentoSriCola, tarea_id)
        documento = session.exec(
            select(DocumentoElectronico).where(DocumentoElectronico.venta_id == venta_id)
        ).first()
        historial = session.exec(
            select(DocumentoElectronicoHistorial).where(
                DocumentoElectronicoHistorial.entidad_id == documento.id
            )
        ).all()

        assert venta is not None
        assert tarea is not None
        assert documento is not None
        assert venta.estado_sri == EstadoSriDocumento.RECHAZADO
        assert venta.sri_ultimo_error == "Clave de acceso duplicada"
        assert tarea.estado == EstadoColaSri.FALLIDO
        assert documento.estado == EstadoDocumentoElectronico.RECHAZADO
        assert any("Clave de acceso duplicada" in h.motivo_cambio for h in historial)
        assert reintentos == []
        assert correos == []


def test_worker_sri_autorizado_gatilla_correo():
    engine = _build_test_engine()

    class GatewayAutorizado:
        def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
            _ = (tipo_documento, payload)
            return {"estado": "AUTORIZADO", "mensaje": "Documento autorizado"}

    service = VentaSriAsyncService(gateway=GatewayAutorizado(), db_engine=engine)

    with Session(engine) as session:
        venta = _crear_venta_electronica(session)
        tarea = service.encolar_venta(
            session,
            venta_id=venta.id,
            usuario_id="sri-bot",
            commit=True,
        )
        tarea_id = tarea.id
        venta_id = venta.id

    correos: list[str] = []
    service.procesar_documento_sri(
        tarea_id,
        scheduler=lambda _task_id, _delay: None,
        email_dispatcher=lambda v_id: correos.append(str(v_id)),
    )

    with Session(engine) as session:
        venta = session.get(Venta, venta_id)
        tarea = session.get(DocumentoSriCola, tarea_id)

        assert venta is not None
        assert tarea is not None
        assert venta.estado_sri == EstadoSriDocumento.AUTORIZADO
        assert tarea.estado == EstadoColaSri.COMPLETADO
        assert correos == [str(venta_id)]


def test_encolar_venta_permite_produccion_y_mapea_ambiente(monkeypatch):
    engine = _build_test_engine()
    service = VentaSriAsyncService(db_engine=engine)

    class FakeSettings:
        FEEC_AMBIENTE = "produccion"
        FEEC_TIPO_EMISION = "1"

    monkeypatch.setattr(
        "osiris.modules.sri.facturacion_electronica.services.fe_mapper_service.get_settings",
        lambda: FakeSettings(),
    )

    with Session(engine) as session:
        venta = _crear_venta_electronica(session)
        tarea = service.encolar_venta(
            session,
            venta_id=venta.id,
            usuario_id="sri-bot",
            commit=True,
        )

        payload = json.loads(tarea.payload_json)
        assert payload["infoTributaria"]["ambiente"] == "2"
