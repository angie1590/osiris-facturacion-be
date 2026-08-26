from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.core_sri.models import (
    EstadoVenta,
    FormaPagoSRI,
    TipoIdentificacionSRI,
    Venta,
    VentaDetalle,
)
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.movimientos.models import InventarioStock
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
            AuditLog.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            PuntoEmision.__table__,
            CasaComercial.__table__,
            Bodega.__table__,
            Producto.__table__,
            InventarioStock.__table__,
            Venta.__table__,
            VentaDetalle.__table__,
        ],
    )
    return engine


def _seed_contexto(session: Session):
    session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
    session.flush()

    empresa = Empresa(
        razon_social="Empresa Reportes",
        nombre_comercial="Empresa Reportes",
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

    sucursal = Sucursal(
        codigo="001",
        nombre="Sucursal Reportes",
        direccion="Av. 1",
        telefono="022000000",
        es_matriz=True,
        empresa_id=empresa.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(sucursal)
    session.flush()

    punto_emision = PuntoEmision(
        codigo="001",
        descripcion="Punto de emision reportes",
        secuencial_actual=1,
        sucursal_id=sucursal.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(punto_emision)

    bodega = Bodega(
        codigo_bodega="BOD-REP-001",
        nombre_bodega="Bodega Reportes",
        empresa_id=empresa.id,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(bodega)

    producto = Producto(
        nombre="Producto Reporte",
        descripcion="Producto para pruebas de reportes",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("20.00"),
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
            cantidad_actual=Decimal("50.0000"),
            costo_promedio_vigente=Decimal("8.0000"),
            usuario_auditoria="seed",
            activo=True,
        )
    )
    session.commit()
    return empresa.id, punto_emision.id, producto.id


def _crear_venta(
    session: Session,
    *,
    empresa_id,
    punto_emision_id,
    producto_id,
    estado: EstadoVenta,
    cantidad: Decimal,
    precio_unitario: Decimal,
    subtotal_0: Decimal,
    subtotal_12: Decimal,
    monto_iva: Decimal,
    total: Decimal,
    fecha_emision: date = date(2026, 2, 21),
):
    venta = Venta(
        empresa_id=empresa_id,
        punto_emision_id=punto_emision_id,
        fecha_emision=fecha_emision,
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador="1790012345001",
        forma_pago=FormaPagoSRI.EFECTIVO,
        subtotal_sin_impuestos=subtotal_0 + subtotal_12,
        subtotal_12=subtotal_12,
        subtotal_15=Decimal("0.00"),
        subtotal_0=subtotal_0,
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=monto_iva,
        monto_ice=Decimal("0.00"),
        valor_total=total,
        estado=estado,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(venta)
    session.flush()

    session.add(
        VentaDetalle(
            venta_id=venta.id,
            producto_id=producto_id,
            descripcion="Detalle reporte",
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            descuento=Decimal("0.00"),
            subtotal_sin_impuesto=cantidad * precio_unitario,
            usuario_auditoria="seed",
            activo=True,
        )
    )
    session.commit()
    return venta


def test_reporte_ventas_excluye_anuladas():
    engine = _build_test_engine()
    with Session(engine) as session:
        empresa_id, punto_emision_id, producto_id = _seed_contexto(session)
        _crear_venta(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            producto_id=producto_id,
            estado=EstadoVenta.EMITIDA,
            cantidad=Decimal("1.0000"),
            precio_unitario=Decimal("100.00"),
            subtotal_0=Decimal("50.00"),
            subtotal_12=Decimal("100.00"),
            monto_iva=Decimal("15.00"),
            total=Decimal("165.00"),
        )
        _crear_venta(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            producto_id=producto_id,
            estado=EstadoVenta.ANULADA,
            cantidad=Decimal("1.0000"),
            precio_unitario=Decimal("999.00"),
            subtotal_0=Decimal("999.00"),
            subtotal_12=Decimal("999.00"),
            monto_iva=Decimal("999.00"),
            total=Decimal("2997.00"),
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/reportes/ventas/resumen",
                params={
                    "fecha_inicio": "2026-02-01",
                    "fecha_fin": "2026-02-28",
                    "punto_emision_id": str(punto_emision_id),
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert Decimal(str(data["subtotal_0"])) == Decimal("50.00")
        assert Decimal(str(data["subtotal_12"])) == Decimal("100.00")
        assert Decimal(str(data["monto_iva"])) == Decimal("15.00")
        assert Decimal(str(data["total"])) == Decimal("165.00")
        assert int(data["total_ventas"]) == 1
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_reporte_tendencias_agrupacion():
    engine = _build_test_engine()
    with Session(engine) as session:
        empresa_id, punto_emision_id, producto_id = _seed_contexto(session)
        _crear_venta(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            producto_id=producto_id,
            estado=EstadoVenta.EMITIDA,
            cantidad=Decimal("1.0000"),
            precio_unitario=Decimal("30.00"),
            subtotal_0=Decimal("30.00"),
            subtotal_12=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            total=Decimal("30.00"),
            fecha_emision=date(2026, 2, 20),
        )
        _crear_venta(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            producto_id=producto_id,
            estado=EstadoVenta.EMITIDA,
            cantidad=Decimal("2.0000"),
            precio_unitario=Decimal("50.00"),
            subtotal_0=Decimal("100.00"),
            subtotal_12=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            total=Decimal("100.00"),
            fecha_emision=date(2026, 2, 21),
        )
        _crear_venta(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            producto_id=producto_id,
            estado=EstadoVenta.ANULADA,
            cantidad=Decimal("1.0000"),
            precio_unitario=Decimal("999.00"),
            subtotal_0=Decimal("999.00"),
            subtotal_12=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            total=Decimal("999.00"),
            fecha_emision=date(2026, 2, 21),
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/reportes/ventas/tendencias",
                params={
                    "fecha_inicio": "2026-02-01",
                    "fecha_fin": "2026-02-28",
                    "agrupacion": "DIARIA",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert [item["periodo"] for item in data] == ["2026-02-20", "2026-02-21"]
        assert Decimal(str(data[0]["total"])) == Decimal("30.00")
        assert int(data[0]["total_ventas"]) == 1
        assert Decimal(str(data[1]["total"])) == Decimal("100.00")
        assert int(data[1]["total_ventas"]) == 1
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_reporte_tendencias_agrupacion_anual():
    engine = _build_test_engine()
    with Session(engine) as session:
        empresa_id, punto_emision_id, producto_id = _seed_contexto(session)
        _crear_venta(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            producto_id=producto_id,
            estado=EstadoVenta.EMITIDA,
            cantidad=Decimal("1.0000"),
            precio_unitario=Decimal("40.00"),
            subtotal_0=Decimal("40.00"),
            subtotal_12=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            total=Decimal("40.00"),
            fecha_emision=date(2025, 12, 15),
        )
        _crear_venta(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            producto_id=producto_id,
            estado=EstadoVenta.EMITIDA,
            cantidad=Decimal("1.0000"),
            precio_unitario=Decimal("70.00"),
            subtotal_0=Decimal("70.00"),
            subtotal_12=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            total=Decimal("70.00"),
            fecha_emision=date(2026, 1, 10),
        )
        _crear_venta(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            producto_id=producto_id,
            estado=EstadoVenta.ANULADA,
            cantidad=Decimal("1.0000"),
            precio_unitario=Decimal("999.00"),
            subtotal_0=Decimal("999.00"),
            subtotal_12=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            total=Decimal("999.00"),
            fecha_emision=date(2026, 5, 10),
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/reportes/ventas/tendencias",
                params={
                    "fecha_inicio": "2025-01-01",
                    "fecha_fin": "2026-12-31",
                    "agrupacion": "ANUAL",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert [item["periodo"] for item in data] == ["2025-01-01", "2026-01-01"]
        assert Decimal(str(data[0]["total"])) == Decimal("40.00")
        assert int(data[0]["total_ventas"]) == 1
        assert Decimal(str(data[1]["total"])) == Decimal("70.00")
        assert int(data[1]["total_ventas"]) == 1
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_top_productos_calcula_margen():
    engine = _build_test_engine()
    with Session(engine) as session:
        empresa_id, punto_emision_id, producto_id = _seed_contexto(session)
        _crear_venta(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            producto_id=producto_id,
            estado=EstadoVenta.EMITIDA,
            cantidad=Decimal("3.0000"),
            precio_unitario=Decimal("20.00"),
            subtotal_0=Decimal("60.00"),
            subtotal_12=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            total=Decimal("60.00"),
        )
        _crear_venta(
            session,
            empresa_id=empresa_id,
            punto_emision_id=punto_emision_id,
            producto_id=producto_id,
            estado=EstadoVenta.ANULADA,
            cantidad=Decimal("10.0000"),
            precio_unitario=Decimal("50.00"),
            subtotal_0=Decimal("500.00"),
            subtotal_12=Decimal("0.00"),
            monto_iva=Decimal("0.00"),
            total=Decimal("500.00"),
        )

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/reportes/ventas/top-productos",
                params={
                    "fecha_inicio": "2026-02-01",
                    "fecha_fin": "2026-02-28",
                    "punto_emision_id": str(punto_emision_id),
                },
            )
        assert response.status_code == 200, response.text
        items = response.json()
        assert len(items) == 1
        top = items[0]
        assert top["nombre_producto"] == "Producto Reporte"
        assert Decimal(str(top["cantidad_vendida"])) == Decimal("3.0000")
        assert Decimal(str(top["total_dolares_vendido"])) == Decimal("60.00")
        # Ganancia = (20 - 8) * 3 = 36.00
        assert Decimal(str(top["ganancia_bruta_estimada"])) == Decimal("36.00")
    finally:
        app.dependency_overrides.pop(get_session, None)
