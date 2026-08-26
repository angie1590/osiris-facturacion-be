from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.core_sri.models import (
    CuentaPorCobrar,
    DocumentoElectronico,
    DocumentoElectronicoHistorial,
    DocumentoSriCola,
    EstadoDocumentoElectronico,
    EstadoSriDocumento,
    EstadoVenta,
    FormaPagoSRI,
    TipoDocumentoElectronico,
    TipoIdentificacionSRI,
    Venta,
    VentaDetalle,
    VentaDetalleImpuesto,
    VentaEstadoHistorial,
)
from osiris.modules.sri.core_sri.all_schemas import q2
from osiris.modules.ventas.services.venta_service import VentaService
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.movimientos.models import (
    InventarioStock,
    MovimientoInventario,
    MovimientoInventarioDetalle,
)
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
            Bodega.__table__,
            CasaComercial.__table__,
            Producto.__table__,
            Venta.__table__,
            VentaDetalle.__table__,
            VentaDetalleImpuesto.__table__,
            MovimientoInventario.__table__,
            MovimientoInventarioDetalle.__table__,
            InventarioStock.__table__,
            CuentaPorCobrar.__table__,
            VentaEstadoHistorial.__table__,
            DocumentoElectronico.__table__,
            DocumentoElectronicoHistorial.__table__,
            DocumentoSriCola.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def _seed_venta_borrador(session: Session) -> Venta:
    tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
    session.add(tipo)

    empresa = Empresa(
        razon_social="Empresa Orquestador FE",
        nombre_comercial="Empresa Orquestador FE",
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

    bodega = Bodega(
        codigo_bodega="BOD-E7-001",
        nombre_bodega="Bodega E7",
        empresa_id=empresa.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(bodega)

    producto = Producto(
        nombre="Producto E7",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        cantidad=0,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(producto)
    session.flush()

    session.add(
        InventarioStock(
            bodega_id=bodega.id,
            producto_id=producto.id,
            cantidad_actual=Decimal("10.0000"),
            costo_promedio_vigente=Decimal("5.0000"),
            usuario_auditoria="seed",
            activo=True,
        )
    )

    subtotal = q2(Decimal("5.0000") * Decimal("10.00"))
    venta = Venta(
        empresa_id=empresa.id,
        fecha_emision=date.today(),
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
        estado=EstadoVenta.BORRADOR,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(venta)
    session.flush()

    session.add(
        VentaDetalle(
            venta_id=venta.id,
            producto_id=producto.id,
            descripcion="Detalle venta E7",
            cantidad=Decimal("5.0000"),
            precio_unitario=Decimal("10.0000"),
            descuento=Decimal("0.00"),
            subtotal_sin_impuesto=subtotal,
            usuario_auditoria="seed",
            activo=True,
        )
    )
    session.commit()
    session.refresh(venta)
    return venta


def test_encolar_documento_crea_registro():
    engine = _build_test_engine()
    service = VentaService()
    service.venta_sri_async_service.db_engine = engine
    service.orquestador_fe_service.db_engine = engine

    with Session(engine) as session:
        venta = _seed_venta_borrador(session)
        emitida = service.emitir_venta(
            session,
            venta.id,
            usuario_auditoria="qa.user",
            encolar_sri=True,
        )

        documento = session.exec(
            select(DocumentoElectronico).where(
                DocumentoElectronico.tipo_documento == TipoDocumentoElectronico.FACTURA,
                DocumentoElectronico.referencia_id == emitida.id,
                DocumentoElectronico.activo.is_(True),
            )
        ).one_or_none()

        assert documento is not None
        assert documento.estado_sri == EstadoDocumentoElectronico.EN_COLA


def test_procesar_documento_cambia_estado():
    engine = _build_test_engine()
    service = VentaService()
    service.venta_sri_async_service.db_engine = engine
    service.orquestador_fe_service.db_engine = engine
    service.orquestador_fe_service.venta_sri_service.db_engine = engine

    class GatewayAutorizado:
        def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
            _ = (tipo_documento, payload)
            return {"estado": "AUTORIZADO", "mensaje": "Documento autorizado"}

    with Session(engine) as session:
        venta = _seed_venta_borrador(session)
        emitida = service.emitir_venta(
            session,
            venta.id,
            usuario_auditoria="qa.user",
            encolar_sri=True,
        )

        documento = session.exec(
            select(DocumentoElectronico).where(
                DocumentoElectronico.tipo_documento == TipoDocumentoElectronico.FACTURA,
                DocumentoElectronico.referencia_id == emitida.id,
                DocumentoElectronico.activo.is_(True),
            )
        ).one()
        documento_id = documento.id

    service.orquestador_fe_service.procesar_documento(
        documento_id,
        venta_gateway=GatewayAutorizado(),
    )

    with Session(engine) as session:
        documento = session.get(DocumentoElectronico, documento_id)
        assert documento is not None
        assert documento.estado_sri == EstadoDocumentoElectronico.AUTORIZADO
        venta = session.get(Venta, documento.referencia_id)
        assert venta is not None
        assert venta.estado_sri == EstadoSriDocumento.AUTORIZADO


def test_retry_backoff_incrementa_tiempo():
    engine = _build_test_engine()
    service = VentaService()
    service.venta_sri_async_service.db_engine = engine
    service.orquestador_fe_service.db_engine = engine
    service.orquestador_fe_service.venta_sri_service.db_engine = engine

    class GatewayTimeout:
        def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
            _ = (tipo_documento, payload)
            raise TimeoutError("SRI timeout")

    with Session(engine) as session:
        venta = _seed_venta_borrador(session)
        emitida = service.emitir_venta(
            session,
            venta.id,
            usuario_auditoria="qa.user",
            encolar_sri=True,
        )
        documento = session.exec(
            select(DocumentoElectronico).where(
                DocumentoElectronico.tipo_documento == TipoDocumentoElectronico.FACTURA,
                DocumentoElectronico.referencia_id == emitida.id,
                DocumentoElectronico.activo.is_(True),
            )
        ).one()
        documento_id = documento.id
        retry_inicial = documento.next_retry_at

    service.orquestador_fe_service.procesar_documento(
        documento_id,
        venta_gateway=GatewayTimeout(),
    )

    with Session(engine) as session:
        documento = session.get(DocumentoElectronico, documento_id)
        assert documento is not None
        assert documento.intentos == 1
        assert documento.estado_sri in {
            EstadoDocumentoElectronico.EN_COLA,
            EstadoDocumentoElectronico.RECIBIDO,
        }
        assert documento.next_retry_at is not None
        assert retry_inicial is not None
        assert documento.next_retry_at > retry_inicial


def test_rechazo_detiene_reintentos():
    engine = _build_test_engine()
    service = VentaService()
    service.venta_sri_async_service.db_engine = engine
    service.orquestador_fe_service.db_engine = engine
    service.orquestador_fe_service.venta_sri_service.db_engine = engine

    class GatewayRechazado:
        def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
            _ = (tipo_documento, payload)
            return {"estado": "RECHAZADO", "mensaje": "XML inválido"}

    with Session(engine) as session:
        venta = _seed_venta_borrador(session)
        emitida = service.emitir_venta(
            session,
            venta.id,
            usuario_auditoria="qa.user",
            encolar_sri=True,
        )
        documento = session.exec(
            select(DocumentoElectronico).where(
                DocumentoElectronico.tipo_documento == TipoDocumentoElectronico.FACTURA,
                DocumentoElectronico.referencia_id == emitida.id,
                DocumentoElectronico.activo.is_(True),
            )
        ).one()
        documento_id = documento.id

    service.orquestador_fe_service.procesar_documento(
        documento_id,
        venta_gateway=GatewayRechazado(),
    )

    with Session(engine) as session:
        documento = session.get(DocumentoElectronico, documento_id)
        assert documento is not None
        assert documento.estado_sri == EstadoDocumentoElectronico.RECHAZADO
        assert documento.next_retry_at is None
