from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.compras.services.compra_service import CompraService
from osiris.modules.compras.services.cxp_service import CuentaPorPagarService
from osiris.modules.sri.core_sri.models import (
    Compra,
    CompraDetalle,
    CompraDetalleImpuesto,
    CuentaPorPagar,
    EstadoCuentaPorPagar,
    FormaPagoSRI,
    PagoCxP,
    Retencion,
    RetencionDetalle,
    TipoRetencionSRI,
)
from osiris.modules.sri.core_sri.all_schemas import (
    CompraCreate,
    PagoCxPCreate,
    RetencionCreate,
    RetencionDetalleCreate,
    RetencionEmitRequest,
    VentaCompraDetalleCreate,
)
from osiris.modules.compras.services.retencion_service import RetencionService
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
            Compra.__table__,
            CompraDetalle.__table__,
            CompraDetalleImpuesto.__table__,
            CuentaPorPagar.__table__,
            PagoCxP.__table__,
            Retencion.__table__,
            RetencionDetalle.__table__,
            MovimientoInventario.__table__,
            MovimientoInventarioDetalle.__table__,
            InventarioStock.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def test_flujo_administrativo_compras_cxp_retencion():
    engine = _build_test_engine()
    compra_service = CompraService()
    retencion_service = RetencionService()
    cxp_service = CuentaPorPagarService()

    with Session(engine) as session:
        tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
        session.add(tipo)

        empresa = Empresa(
            razon_social="Proveedor Flujo CxP",
            nombre_comercial="Proveedor Flujo CxP",
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

        bodega = Bodega(
            codigo_bodega="BOD-FLUJO-001",
            nombre_bodega="Bodega Flujo",
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(bodega)

        producto = Producto(
            nombre="Producto Flujo Retencion",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(producto)
        session.commit()

        compra = compra_service.registrar_compra(
            session,
            CompraCreate(
                proveedor_id=empresa.id,
                secuencial_factura="001-001-123456789",
                autorizacion_sri="1" * 49,
                fecha_emision=date.today(),
                bodega_id=bodega.id,
                sustento_tributario="01",
                tipo_identificacion_proveedor="RUC",
                identificacion_proveedor="1790099988001",
                forma_pago=FormaPagoSRI.TRANSFERENCIA,
                usuario_auditoria="compras.user",
                detalles=[
                    VentaCompraDetalleCreate(
                        producto_id=producto.id,
                        descripcion="Compra flujo",
                        cantidad=Decimal("10.0000"),
                        precio_unitario=Decimal("10.0000"),
                        descuento=Decimal("0.00"),
                        impuestos=[],
                    )
                ],
            ),
        )

        cxp = session.exec(
            select(CuentaPorPagar).where(CuentaPorPagar.compra_id == compra.id)
        ).one()
        assert cxp.saldo_pendiente == Decimal("100.00")

        retencion = retencion_service.crear_retencion(
            session,
            compra.id,
            RetencionCreate(
                usuario_auditoria="ret.user",
                detalles=[
                    RetencionDetalleCreate(
                        codigo_retencion_sri="303",
                        tipo=TipoRetencionSRI.RENTA,
                        porcentaje=Decimal("10.00"),
                        base_calculo=Decimal("100.00"),
                    )
                ],
            ),
        )
        retencion_service.emitir_retencion(
            session,
            retencion.id,
            RetencionEmitRequest(
                usuario_auditoria="ret.user",
                encolar=False,
            ),
        )

        session.refresh(cxp)
        assert cxp.valor_retenido == Decimal("10.00")
        assert cxp.saldo_pendiente == Decimal("90.00")

        cxp_service.registrar_pago_cxp(
            session,
            cxp.id,
            PagoCxPCreate(
                monto=Decimal("90.00"),
                fecha=date.today(),
                forma_pago=FormaPagoSRI.TRANSFERENCIA,
                usuario_auditoria="tesoreria.user",
            ),
        )

        session.refresh(cxp)
        assert cxp.estado == EstadoCuentaPorPagar.PAGADA
        assert cxp.saldo_pendiente == Decimal("0.00")
