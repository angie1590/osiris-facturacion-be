from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.modules.sri.core_sri.models import (
    Compra,
    DocumentoSriCola,
    EstadoColaSri,
    EstadoRetencion,
    EstadoSriDocumento,
    FormaPagoSRI,
    Retencion,
    RetencionDetalle,
    RetencionEstadoHistorial,
    SustentoTributarioSRI,
    TipoIdentificacionSRI,
    TipoRetencionSRI,
)
from osiris.modules.sri.facturacion_electronica.services.sri_async_service import SriAsyncService


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Compra.__table__,
            Retencion.__table__,
            RetencionDetalle.__table__,
            DocumentoSriCola.__table__,
            RetencionEstadoHistorial.__table__,
        ],
    )
    return engine


def _crear_compra_retencion(session: Session) -> Retencion:
    compra = Compra(
        proveedor_id=uuid4(),
        secuencial_factura="001-001-123456789",
        autorizacion_sri="1" * 49,
        fecha_emision=date.today(),
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
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(compra)
    session.flush()

    retencion = Retencion(
        compra_id=compra.id,
        fecha_emision=date.today(),
        estado=EstadoRetencion.ENCOLADA,
        estado_sri=EstadoSriDocumento.PENDIENTE,
        total_retenido=Decimal("10.00"),
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(retencion)
    session.flush()
    session.add(
        RetencionDetalle(
            retencion_id=retencion.id,
            codigo_retencion_sri="303",
            tipo=TipoRetencionSRI.RENTA,
            porcentaje=Decimal("10.00"),
            base_calculo=Decimal("100.00"),
            valor_retenido=Decimal("10.00"),
            usuario_auditoria="seed",
            activo=True,
        )
    )
    session.commit()
    session.refresh(retencion)
    return retencion


def test_cola_procesamiento_exitoso():
    engine = _build_test_engine()

    class GatewayAutorizado:
        def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
            _ = (tipo_documento, payload)
            return {"estado": "AUTORIZADO", "mensaje": "Autorizado"}

    sri_service = SriAsyncService(gateway=GatewayAutorizado(), db_engine=engine)
    with Session(engine) as session:
        retencion = _crear_compra_retencion(session)
        retencion_id = retencion.id
        tarea = sri_service.encolar_retencion(
            session,
            retencion_id=retencion_id,
            usuario_id="sri-bot",
            commit=True,
        )
        tarea_id = tarea.id

    sri_service.procesar_documento_sri(tarea_id, scheduler=lambda _task_id, _delay: None)

    with Session(engine) as session:
        retencion_db = session.get(Retencion, retencion_id)
        tarea_db = session.get(DocumentoSriCola, tarea_id)
        assert retencion_db is not None
        assert tarea_db is not None
        assert retencion_db.estado_sri == EstadoSriDocumento.AUTORIZADO
        assert tarea_db.estado == EstadoColaSri.COMPLETADO


def test_reintentos_sri_timeout():
    engine = _build_test_engine()

    class GatewayTimeout:
        def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
            _ = (tipo_documento, payload)
            raise TimeoutError("SRI timeout")

    sri_service = SriAsyncService(gateway=GatewayTimeout(), db_engine=engine)
    with Session(engine) as session:
        retencion = _crear_compra_retencion(session)
        retencion_id = retencion.id
        tarea = sri_service.encolar_retencion(
            session,
            retencion_id=retencion_id,
            usuario_id="sri-bot",
            commit=True,
        )
        tarea_id = tarea.id

    reencolados: list[tuple[str, int]] = []

    def _scheduler(task_id, delay: int):
        reencolados.append((str(task_id), delay))

    sri_service.procesar_documento_sri(tarea_id, scheduler=_scheduler)

    with Session(engine) as session:
        retencion_db = session.get(Retencion, retencion_id)
        tarea_db = session.get(DocumentoSriCola, tarea_id)
        assert retencion_db is not None
        assert tarea_db is not None
        assert tarea_db.intentos_realizados == 1
        assert tarea_db.estado == EstadoColaSri.REINTENTO_PROGRAMADO
        assert retencion_db.estado_sri == EstadoSriDocumento.REINTENTO
        assert len(reencolados) == 1
        assert reencolados[0][0] == str(tarea_id)
        assert reencolados[0][1] == 1
