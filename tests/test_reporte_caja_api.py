from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.core_sri.types import (
    EstadoCuentaPorCobrar,
    EstadoRetencionRecibida,
    EstadoVenta,
    FormaPagoSRI,
    TipoIdentificacionSRI,
)
from osiris.modules.ventas.models import CuentaPorCobrar, PagoCxC, RetencionRecibida, Venta
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
            Empresa.__table__,
            Sucursal.__table__,
            PuntoEmision.__table__,
            Venta.__table__,
            CuentaPorCobrar.__table__,
            PagoCxC.__table__,
            RetencionRecibida.__table__,
        ],
    )
    return engine


def _seed_empresa(session: Session):
    session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
    session.flush()
    empresa = Empresa(
        razon_social="Empresa Caja",
        nombre_comercial="Empresa Caja",
        ruc="1790011122001",
        direccion_matriz="Av. Caja",
        telefono="022111222",
        obligado_contabilidad=True,
        regimen="GENERAL",
        modo_emision="ELECTRONICO",
        tipo_contribuyente_id="01",
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(empresa)
    session.flush()
    sucursal = Sucursal(
        codigo="001",
        nombre="Sucursal Caja",
        direccion="Av. Caja 123",
        telefono="022111333",
        es_matriz=True,
        empresa_id=empresa.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(sucursal)
    session.flush()
    session.add(
        PuntoEmision(
            codigo="001",
            descripcion="Punto Caja",
            secuencial_actual=1,
            sucursal_id=sucursal.id,
            usuario_auditoria="seed",
            activo=True,
        )
    )
    session.commit()
    return empresa.id


def _crear_venta(session: Session, *, empresa_id, total: Decimal) -> tuple[Venta, CuentaPorCobrar]:
    venta = Venta(
        empresa_id=empresa_id,
        cliente_id=uuid4(),
        fecha_emision=date.today(),
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador=str(uuid4().int)[:13],
        forma_pago=FormaPagoSRI.EFECTIVO,
        subtotal_sin_impuestos=total,
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=total,
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=total,
        estado=EstadoVenta.EMITIDA,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(venta)
    session.flush()
    cxc = CuentaPorCobrar(
        venta_id=venta.id,
        valor_total_factura=total,
        valor_retenido=Decimal("0.00"),
        pagos_acumulados=Decimal("0.00"),
        saldo_pendiente=total,
        estado=EstadoCuentaPorCobrar.PENDIENTE,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(cxc)
    session.flush()
    return venta, cxc


def test_reporte_cierre_caja_agrupa_formas_pago():
    engine = _build_test_engine()
    with Session(engine) as session:
        empresa_id = _seed_empresa(session)

        venta_cobrada, cxc_cobrada = _crear_venta(session, empresa_id=empresa_id, total=Decimal("100.00"))
        _, _ = _crear_venta(session, empresa_id=empresa_id, total=Decimal("500.00"))  # Emitida, no cobrada.

        session.add(
            PagoCxC(
                cuenta_por_cobrar_id=cxc_cobrada.id,
                monto=Decimal("40.00"),
                fecha=date.today(),
                forma_pago_sri=FormaPagoSRI.EFECTIVO,
                usuario_auditoria="cashier",
                activo=True,
            )
        )
        session.add(
            PagoCxC(
                cuenta_por_cobrar_id=cxc_cobrada.id,
                monto=Decimal("60.00"),
                fecha=date.today(),
                forma_pago_sri=FormaPagoSRI.TRANSFERENCIA,
                usuario_auditoria="cashier",
                activo=True,
            )
        )
        session.add(
            PagoCxC(
                cuenta_por_cobrar_id=cxc_cobrada.id,
                monto=Decimal("99.00"),
                fecha=date.today() - timedelta(days=1),
                forma_pago_sri=FormaPagoSRI.EFECTIVO,
                usuario_auditoria="cashier",
                activo=True,
            )
        )

        session.add(
            RetencionRecibida(
                venta_id=venta_cobrada.id,
                cliente_id=venta_cobrada.cliente_id or uuid4(),
                numero_retencion="001-001-000000321",
                fecha_emision=date.today(),
                estado=EstadoRetencionRecibida.APLICADA,
                total_retenido=Decimal("10.00"),
                usuario_auditoria="cashier",
                activo=True,
            )
        )
        session.add(
            RetencionRecibida(
                venta_id=venta_cobrada.id,
                cliente_id=venta_cobrada.cliente_id or uuid4(),
                numero_retencion="001-001-000000322",
                fecha_emision=date.today(),
                estado=EstadoRetencionRecibida.BORRADOR,
                total_retenido=Decimal("999.00"),
                usuario_auditoria="cashier",
                activo=True,
            )
        )

        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/reportes/caja/cierre-diario",
                params={"fecha": date.today().isoformat()},
            )
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["fecha"] == date.today().isoformat()
        assert Decimal(str(data["dinero_liquido"]["total"])) == Decimal("100.00")
        assert Decimal(str(data["credito_tributario"]["total_retenciones"])) == Decimal("10.00")

        montos_por_forma = {
            item["forma_pago_sri"]: Decimal(str(item["monto"]))
            for item in data["dinero_liquido"]["por_forma_pago"]
        }
        assert montos_por_forma["EFECTIVO"] == Decimal("40.00")
        assert montos_por_forma["TRANSFERENCIA"] == Decimal("60.00")
        assert len(montos_por_forma) == 2
    finally:
        app.dependency_overrides.pop(get_session, None)
