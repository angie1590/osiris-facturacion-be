from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa, RegimenTributario
from osiris.modules.sri.core_sri.models import (
    EstadoVenta,
    FormaPagoSRI,
    TipoIdentificacionSRI,
    Venta,
    VentaDetalle,
    VentaDetalleImpuesto,
)
from osiris.modules.sri.core_sri.all_schemas import ImpuestoAplicadoInput, VentaCompraDetalleCreate, VentaCreate, VentaUpdate
from osiris.modules.ventas.services.venta_service import VentaService
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
            CasaComercial.__table__,
            Producto.__table__,
            Venta.__table__,
            VentaDetalle.__table__,
            VentaDetalleImpuesto.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def test_rimpe_np_fuerza_nota_venta():
    engine = _build_test_engine()
    service = VentaService()
    service._orquestar_egreso_inventario = lambda _session, _venta, _payload: None  # type: ignore[method-assign]

    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        session.flush()

        empresa = Empresa(
            razon_social="Empresa RIMPE",
            nombre_comercial="Empresa RIMPE",
            ruc="1790012345001",
            direccion_matriz="Av. Principal",
            telefono="022345678",
            obligado_contabilidad=False,
            regimen=RegimenTributario.RIMPE_NEGOCIO_POPULAR,
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(empresa)

        producto = Producto(
            nombre=f"Producto-{uuid4().hex[:8]}",
            tipo=TipoProducto.SERVICIO,
            pvp=Decimal("100.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(producto)
        session.commit()

        payload = VentaCreate(
            empresa_id=empresa.id,
            tipo_identificacion_comprador="RUC",
            identificacion_comprador="1790012345001",
            forma_pago="EFECTIVO",
            usuario_auditoria="tester",
            detalles=[
                VentaCompraDetalleCreate(
                    producto_id=producto.id,
                    descripcion="Servicio no excluido",
                    cantidad=Decimal("1"),
                    precio_unitario=Decimal("100"),
                    es_actividad_excluida=False,
                    impuestos=[
                        ImpuestoAplicadoInput(
                            tipo_impuesto="IVA",
                            codigo_impuesto_sri="2",
                            codigo_porcentaje_sri="4",
                            tarifa=Decimal("15"),
                        )
                    ],
                )
            ],
        )

        with pytest.raises(HTTPException) as exc:
            service.registrar_venta(session, payload)

        assert exc.value.status_code == 400
        assert "0% de IVA" in exc.value.detail


def test_actualizar_venta_emitida_bloquea():
    engine = _build_test_engine()
    service = VentaService()

    with Session(engine) as session:
        venta = Venta(
            fecha_emision=date.today(),
            tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
            identificacion_comprador="1790012345001",
            forma_pago=FormaPagoSRI.EFECTIVO,
            subtotal_sin_impuestos=Decimal("100.00"),
            subtotal_12=Decimal("0.00"),
            subtotal_15=Decimal("100.00"),
            subtotal_0=Decimal("0.00"),
            subtotal_no_objeto=Decimal("0.00"),
            monto_iva=Decimal("15.00"),
            monto_ice=Decimal("0.00"),
            valor_total=Decimal("115.00"),
            estado=EstadoVenta.EMITIDA,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(venta)
        session.commit()

        with pytest.raises(HTTPException) as exc:
            service.actualizar_venta(
                session,
                venta.id,
                VentaUpdate(
                    identificacion_comprador="1790012345999",
                    usuario_auditoria="tester",
                ),
            )

        assert exc.value.status_code == 400
        assert "estado EMITIDA" in exc.value.detail
