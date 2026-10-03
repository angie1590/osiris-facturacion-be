from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from osiris.core.audit_context import reset_current_company_id, set_current_company_id
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.producto.entity import Producto, TipoProducto
from osiris.modules.sri.core_sri.schemas import ImpuestoAplicadoInput, VentaCompraDetalleCreate
from osiris.modules.sri.core_sri.types import TipoImpuestoMVP
from osiris.modules.sri.medidas_temporales.entity import (
    EstadoMedidaTemporal,
    MedidaTributariaProducto,
    MedidaTributariaTemporal,
    TipoComponenteTributario,
)
from osiris.modules.sri.medidas_temporales.models import MedidaProductoInput, MedidaTributariaCreate
from osiris.modules.sri.medidas_temporales.service import MedidaTributariaService
from osiris.modules.sri.medidas_temporales.router import _require_admin
from osiris.modules.sri.core_sri.models import (
    CuentaPorCobrar,
    Venta,
    VentaDetalle,
    VentaDetalleImpuesto,
    VentaEstadoHistorial,
)
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.modules.common.empresa.entity import RegimenTributario
from osiris.modules.ventas.schemas import VentaCreate
from osiris.modules.ventas.services.venta_service import VentaService


def _engine():
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
            AuditLog.__table__,
            CasaComercial.__table__,
            Sucursal.__table__,
            PuntoEmision.__table__,
            Producto.__table__,
            MedidaTributariaTemporal.__table__,
            MedidaTributariaProducto.__table__,
            Venta.__table__,
            VentaDetalle.__table__,
            VentaDetalleImpuesto.__table__,
            CuentaPorCobrar.__table__,
            VentaEstadoHistorial.__table__,
        ],
    )
    return engine


def _registrar_venta_con_scope(session: Session, empresa: Empresa, payload: VentaCreate):
    token = set_current_company_id(str(empresa.id))
    service = VentaService()
    service._orquestar_egreso_inventario = lambda _session, _venta, _payload: None  # type: ignore[method-assign]
    try:
        return service.registrar_venta(session, payload)
    finally:
        reset_current_company_id(token)


def _seed_empresa_producto(session: Session) -> tuple[Empresa, Producto]:
    tipo = session.get(TipoContribuyente, "01")
    if not tipo:
        session.add(TipoContribuyente(codigo="01", nombre="Persona natural", activo=True))
    empresa = Empresa(
        razon_social="Empresa Turística",
        ruc="1790012345001",
        direccion_matriz="Av. Principal",
        regimen=RegimenTributario.GENERAL,
        modo_emision="ELECTRONICO",
        tipo_contribuyente_id="01",
        usuario_auditoria="tester",
        activo=True,
    )
    producto = Producto(
        nombre=f"Servicio turístico {uuid4().hex[:6]}",
        tipo=TipoProducto.SERVICIO,
        pvp=Decimal("100.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    session.add(empresa)
    session.add(producto)
    session.commit()
    return empresa, producto


def _create_measure(
    session: Session,
    empresa: Empresa,
    producto: Producto,
    *,
    tipo: str = "IVA",
    component: TipoComponenteTributario = TipoComponenteTributario.PORCENTUAL,
    start: date = date(2026, 10, 9),
    end: date = date(2026, 10, 11),
    rate: str = "8.00",
    factor: str | None = None,
    unit: str | None = None,
    code_confirmed: bool = True,
) -> MedidaTributariaTemporal:
    payload = MedidaTributariaCreate(
        empresa_id=empresa.id,
        nombre="Decreto temporal de prueba",
        referencia_legal="Decreto Ejecutivo de prueba número 2026-001",
        tipo_impuesto=tipo,
        componente=component,
        fecha_inicio=start,
        fecha_fin=end,
        codigo_impuesto_sri="2" if tipo == "IVA" else "3",
        codigo_porcentaje_sri="8" if tipo == "IVA" else "999",
        codigo_sri_confirmado=code_confirmed,
        tarifa=Decimal(rate),
        productos=[MedidaProductoInput(producto_id=producto.id, factor_cantidad=factor, unidad_gravable=unit)],
    )
    return MedidaTributariaService().create(session, payload)


def test_ice_especifico_calcula_sobre_litros_de_alcohol_puro_y_permite_ad_valorem():
    detail = VentaCompraDetalleCreate(
        producto_id=uuid4(),
        descripcion="Cerveza artesanal 5% alc. vol.",
        cantidad=Decimal("10"),
        precio_unitario=Decimal("2.00"),
        impuestos=[
            ImpuestoAplicadoInput(
                tipo_impuesto=TipoImpuestoMVP.ICE,
                codigo_impuesto_sri="3",
                codigo_porcentaje_sri="999",
                tarifa=Decimal("1.56"),
                componente=TipoComponenteTributario.ESPECIFICO,
                unidad_gravable="LITRO_ALCOHOL_PURO",
                factor_cantidad=Decimal("0.05"),
            ),
            ImpuestoAplicadoInput(
                tipo_impuesto=TipoImpuestoMVP.ICE,
                codigo_impuesto_sri="3",
                codigo_porcentaje_sri="998",
                tarifa=Decimal("0"),
                componente=TipoComponenteTributario.AD_VALOREM,
            ),
            ImpuestoAplicadoInput(
                tipo_impuesto=TipoImpuestoMVP.IVA,
                codigo_impuesto_sri="2",
                codigo_porcentaje_sri="8",
                tarifa=Decimal("8"),
            ),
        ],
    )

    specific = next(tax for tax in detail.ice_impuestos() if tax.componente == TipoComponenteTributario.ESPECIFICO)
    ad_valorem = next(tax for tax in detail.ice_impuestos() if tax.componente == TipoComponenteTributario.AD_VALOREM)
    iva = detail.iva_impuesto()

    assert detail.base_imponible_impuesto(specific) == Decimal("0.5000")
    assert detail.valor_impuesto(specific) == Decimal("0.78")
    assert detail.valor_impuesto(ad_valorem) == Decimal("0.00")
    assert iva is not None
    assert detail.base_imponible_impuesto(iva) == Decimal("20.78")
    assert detail.valor_impuesto(iva) == Decimal("1.66")


def test_medida_temporal_aplica_en_fechas_inclusivas_y_solo_al_producto_eligibile():
    engine = _engine()
    service = MedidaTributariaService()
    with Session(engine) as session:
        empresa, eligible_product = _seed_empresa_producto(session)
        other_product = Producto(
            nombre=f"Servicio no elegible {uuid4().hex[:6]}",
            tipo=TipoProducto.SERVICIO,
            pvp=Decimal("100.00"),
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(other_product)
        session.commit()
        measure = _create_measure(session, empresa, eligible_product)
        measure.estado = EstadoMedidaTemporal.ACTIVA
        session.add(measure)
        session.commit()

        def sale(product: Producto, emitted: date):
            return service.resolve_sale(
                session,
                VentaCreate(
                    empresa_id=empresa.id,
                    fecha_emision=emitted,
                    tipo_identificacion_comprador="RUC",
                    identificacion_comprador="1790012345001",
                    forma_pago="EFECTIVO",
                    usuario_auditoria="tester",
                    detalles=[
                        VentaCompraDetalleCreate(
                            producto_id=product.id,
                            descripcion=product.nombre,
                            cantidad=Decimal("1"),
                            precio_unitario=Decimal("100.00"),
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
                ),
                empresa_id=empresa.id,
            )

        on_start = sale(eligible_product, date(2026, 10, 9))
        on_end = sale(eligible_product, date(2026, 10, 11))
        before_start = sale(eligible_product, date(2026, 10, 8))
        in_period_other_product = sale(other_product, date(2026, 10, 10))

        assert on_start.detalles[0].iva_impuesto().tarifa == Decimal("8.00")
        assert on_end.detalles[0].iva_impuesto().tarifa == Decimal("8.00")
        assert on_start.detalles[0].iva_impuesto().medida_temporal_id == measure.id
        assert before_start.detalles[0].iva_impuesto().tarifa == Decimal("15.00")
        assert before_start.detalles[0].iva_impuesto().medida_temporal_id is None
        assert in_period_other_product.detalles[0].iva_impuesto().tarifa == Decimal("15.00")


def test_activacion_rechaza_medidas_solapadas_para_mismo_producto_componente():
    engine = _engine()
    service = MedidaTributariaService()
    with Session(engine) as session:
        empresa, product = _seed_empresa_producto(session)
        first = _create_measure(session, empresa, product)
        service.set_state(session, first.id, EstadoMedidaTemporal.ACTIVA, actor="admin")
        second = _create_measure(session, empresa, product, rate="5.00")

        with pytest.raises(HTTPException) as error:
            service.set_state(session, second.id, EstadoMedidaTemporal.ACTIVA, actor="admin")

        assert error.value.status_code == 409
        assert "superpuesta" in error.value.detail
        session.refresh(second)
        assert second.estado == EstadoMedidaTemporal.BORRADOR


def test_activacion_requiere_confirmacion_del_codigo_sri():
    engine = _engine()
    service = MedidaTributariaService()
    with Session(engine) as session:
        empresa, product = _seed_empresa_producto(session)
        measure = _create_measure(session, empresa, product, code_confirmed=False)

        with pytest.raises(HTTPException, match="Confirme el código"):
            service.set_state(session, measure.id, EstadoMedidaTemporal.ACTIVA, actor="admin")

        session.refresh(measure)
        assert measure.estado == EstadoMedidaTemporal.BORRADOR


def test_creacion_rechaza_producto_inexistente_sin_persistir_medida():
    engine = _engine()
    service = MedidaTributariaService()
    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Persona natural", activo=True))
        company = Empresa(
            razon_social="Empresa temporal",
            ruc="1790012345001",
            direccion_matriz="Av. Principal",
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(company)
        session.commit()
        payload = MedidaTributariaCreate(
            empresa_id=company.id,
            nombre="Medida inválida",
            referencia_legal="Decreto Ejecutivo número 2026-001",
            tipo_impuesto="IVA",
            componente=TipoComponenteTributario.PORCENTUAL,
            fecha_inicio=date(2026, 10, 9),
            fecha_fin=date(2026, 10, 11),
            codigo_impuesto_sri="2",
            codigo_porcentaje_sri="8",
            codigo_sri_confirmado=False,
            tarifa=Decimal("8.00"),
            productos=[MedidaProductoInput(producto_id=uuid4())],
        )
        with pytest.raises(HTTPException) as error:
            service.create(session, payload)

        assert error.value.status_code == 400
        assert session.exec(select(MedidaTributariaTemporal)).all() == []


@pytest.mark.parametrize("role_name,allowed", [("admin", True), ("supervisor", False)])
def test_solo_admin_puede_gestionar_medidas(role_name: str, allowed: bool):
    role = SimpleNamespace(nombre=role_name)
    session = SimpleNamespace(get=lambda _model, _role_id: role)
    user = SimpleNamespace(rol_id=uuid4())

    if allowed:
        assert _require_admin(user, session) is None
    else:
        with pytest.raises(HTTPException) as error:
            _require_admin(user, session)
        assert error.value.status_code == 403


def test_venta_guarda_snapshot_tarifa_legal_y_subtotal_iva_ocho():
    engine = _engine()
    with Session(engine) as session:
        empresa, product = _seed_empresa_producto(session)
        measure = _create_measure(session, empresa, product)
        measure.estado = EstadoMedidaTemporal.ACTIVA
        session.add(measure)
        session.commit()

        sale = _registrar_venta_con_scope(
            session,
            empresa,
            VentaCreate(
                empresa_id=empresa.id,
                fecha_emision=date(2026, 10, 10),
                tipo_identificacion_comprador="RUC",
                identificacion_comprador="1790012345001",
                forma_pago="EFECTIVO",
                usuario_auditoria="tester",
                detalles=[
                    VentaCompraDetalleCreate(
                        producto_id=product.id,
                        descripcion=product.nombre,
                        cantidad=Decimal("1"),
                        precio_unitario=Decimal("100"),
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
            ),
        )

        detail = session.exec(select(VentaDetalle).where(VentaDetalle.venta_id == sale.id)).one()
        snapshot = session.exec(
            select(VentaDetalleImpuesto).where(VentaDetalleImpuesto.venta_detalle_id == detail.id)
        ).one()
        sale_read_subtotal = sale.subtotal_8

        assert snapshot is not None
        assert snapshot.tarifa == Decimal("8.00")
        assert snapshot.codigo_porcentaje_sri == "8"
        assert snapshot.medida_temporal_id == measure.id
        assert snapshot.referencia_legal_temporal == measure.referencia_legal
        assert sale.monto_iva == Decimal("8.00")
        assert sale_read_subtotal == Decimal("100.00")


def test_venta_congela_ice_especifico_y_factor_de_alcohol_en_snapshot():
    engine = _engine()
    with Session(engine) as session:
        empresa, product = _seed_empresa_producto(session)
        measure = _create_measure(
            session,
            empresa,
            product,
            tipo="ICE",
            component=TipoComponenteTributario.ESPECIFICO,
            rate="1.56",
            factor="0.025",
            unit="LITRO_ALCOHOL_PURO",
        )
        measure.estado = EstadoMedidaTemporal.ACTIVA
        session.add(measure)
        session.commit()

        sale = _registrar_venta_con_scope(
            session,
            empresa,
            VentaCreate(
                empresa_id=empresa.id,
                fecha_emision=date(2026, 10, 10),
                tipo_identificacion_comprador="RUC",
                identificacion_comprador="1790012345001",
                forma_pago="EFECTIVO",
                usuario_auditoria="tester",
                detalles=[
                    VentaCompraDetalleCreate(
                        producto_id=product.id,
                        descripcion=product.nombre,
                        cantidad=Decimal("10"),
                        precio_unitario=Decimal("2.00"),
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
            ),
        )

        detail = session.exec(select(VentaDetalle).where(VentaDetalle.venta_id == sale.id)).one()
        snapshot = session.exec(
            select(VentaDetalleImpuesto).where(
                VentaDetalleImpuesto.venta_detalle_id == detail.id,
                VentaDetalleImpuesto.tipo_impuesto == "ICE",
            )
        ).one()

        assert snapshot.componente == TipoComponenteTributario.ESPECIFICO
        assert snapshot.unidad_gravable == "LITRO_ALCOHOL_PURO"
        assert snapshot.cantidad_gravable == Decimal("0.2500")
        assert snapshot.tarifa == Decimal("1.560000")
        assert snapshot.valor_impuesto == Decimal("0.39")
        assert snapshot.medida_temporal_id == measure.id

        measure.estado = EstadoMedidaTemporal.INACTIVA
        measure.tarifa = Decimal("0.00")
        session.add(measure)
        session.commit()
        session.refresh(snapshot)
        assert snapshot.tarifa == Decimal("1.560000")
        assert snapshot.valor_impuesto == Decimal("0.39")
        assert snapshot.medida_temporal_id == measure.id
