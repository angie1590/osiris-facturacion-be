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
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.compras.models import Compra, Retencion, RetencionDetalle
from osiris.modules.sri.core_sri.types import (
    EstadoCompra,
    EstadoCuentaPorCobrar,
    EstadoVenta,
    FormaPagoSRI,
    SustentoTributarioSRI,
    TipoIdentificacionSRI,
)
from osiris.modules.ventas.models import (
    CuentaPorCobrar,
    PagoCxC,
    RetencionRecibida,
    RetencionRecibidaDetalle,
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
            AuditLog.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            PuntoEmision.__table__,
            Venta.__table__,
            CuentaPorCobrar.__table__,
            PagoCxC.__table__,
            Compra.__table__,
            Retencion.__table__,
            RetencionDetalle.__table__,
            RetencionRecibida.__table__,
            RetencionRecibidaDetalle.__table__,
        ],
    )
    return engine


def _crear_venta_con_pago(
    session: Session,
    *,
    empresa_id,
    punto_emision_id,
    total: Decimal,
    fecha_emision: date,
) -> None:
    venta = Venta(
        empresa_id=empresa_id,
        punto_emision_id=punto_emision_id,
        fecha_emision=fecha_emision,
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

    session.add(
        PagoCxC(
            cuenta_por_cobrar_id=cxc.id,
            monto=total,
            fecha=date.today(),
            forma_pago_sri=FormaPagoSRI.EFECTIVO,
            usuario_auditoria="seed",
            activo=True,
        )
    )


def _crear_compra(
    session: Session,
    *,
    sucursal_id,
    total: Decimal,
    fecha_emision: date,
) -> None:
    session.add(
        Compra(
            sucursal_id=sucursal_id,
            proveedor_id=uuid4(),
            secuencial_factura=f"001-001-{str(uuid4().int)[-9:]}",
            autorizacion_sri=str(uuid4().int)[:37],
            fecha_emision=fecha_emision,
            sustento_tributario=SustentoTributarioSRI.CREDITO_TRIBUTARIO_BIENES,
            tipo_identificacion_proveedor=TipoIdentificacionSRI.RUC,
            identificacion_proveedor=str(uuid4().int)[:13],
            forma_pago=FormaPagoSRI.TRANSFERENCIA,
            subtotal_sin_impuestos=total,
            subtotal_12=Decimal("0.00"),
            subtotal_15=Decimal("0.00"),
            subtotal_0=total,
            subtotal_no_objeto=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            monto_ice=Decimal("0.00"),
            valor_total=total,
            estado=EstadoCompra.REGISTRADA,
            usuario_auditoria="seed",
            activo=True,
        )
    )


def test_reportes_filtro_sucursal_directo():
    engine = _build_test_engine()
    fecha_mes = date(2026, 2, 15)

    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        session.flush()

        empresa = Empresa(
            razon_social="Empresa Multi-Sucursal",
            nombre_comercial="Empresa Multi-Sucursal",
            ruc="1790012345001",
            direccion_matriz="Av. Matriz",
            telefono="022000111",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(empresa)
        session.flush()

        sucursal_a = Sucursal(
            codigo="001",
            nombre="Matriz",
            direccion="Quito",
            telefono="022000222",
            es_matriz=True,
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        sucursal_b = Sucursal(
            codigo="002",
            nombre="Sucursal B",
            direccion="Guayaquil",
            telefono="042000333",
            es_matriz=False,
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(sucursal_a)
        session.add(sucursal_b)
        session.flush()

        punto_a = PuntoEmision(
            codigo="001",
            descripcion="Punto Matriz",
            secuencial_actual=1,
            sucursal_id=sucursal_a.id,
            usuario_auditoria="seed",
            activo=True,
        )
        punto_b = PuntoEmision(
            codigo="001",
            descripcion="Punto Sucursal B",
            secuencial_actual=1,
            sucursal_id=sucursal_b.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(punto_a)
        session.add(punto_b)
        session.flush()
        sucursal_a_id = sucursal_a.id

        _crear_venta_con_pago(
            session,
            empresa_id=empresa.id,
            punto_emision_id=punto_a.id,
            total=Decimal("100.00"),
            fecha_emision=fecha_mes,
        )
        _crear_venta_con_pago(
            session,
            empresa_id=empresa.id,
            punto_emision_id=punto_b.id,
            total=Decimal("50.00"),
            fecha_emision=fecha_mes,
        )

        _crear_compra(session, sucursal_id=sucursal_a_id, total=Decimal("20.00"), fecha_emision=fecha_mes)
        _crear_compra(session, sucursal_id=sucursal_b.id, total=Decimal("30.00"), fecha_emision=fecha_mes)
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            resumen = client.get(
                "/api/v1/reportes/ventas/resumen",
                params={
                    "fecha_inicio": "2026-02-01",
                    "fecha_fin": "2026-02-28",
                    "sucursal_id": str(sucursal_a_id),
                },
            )
            assert resumen.status_code == 200, resumen.text
            assert Decimal(str(resumen.json()["total"])) == Decimal("100.00")

            caja = client.get(
                "/api/v1/reportes/caja/cierre-diario",
                params={"fecha": date.today().isoformat(), "sucursal_id": str(sucursal_a_id)},
            )
            assert caja.status_code == 200, caja.text
            assert Decimal(str(caja.json()["dinero_liquido"]["total"])) == Decimal("100.00")

            pre_104 = client.get(
                "/api/v1/reportes/impuestos/mensual",
                params={"mes": 2, "anio": 2026, "sucursal_id": str(sucursal_a_id)},
            )
            assert pre_104.status_code == 200, pre_104.text
            assert Decimal(str(pre_104.json()["ventas"]["total"])) == Decimal("100.00")
            assert Decimal(str(pre_104.json()["compras"]["total"])) == Decimal("20.00")
    finally:
        app.dependency_overrides.pop(get_session, None)
