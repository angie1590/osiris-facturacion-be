from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.movimientos.models import (
    EstadoMovimientoInventario,
    InventarioStock,
    MovimientoInventario,
    MovimientoInventarioDetalle,
    TipoMovimientoInventario,
)
from osiris.modules.inventario.movimientos.schemas import MovimientoInventarioCreate, TransferenciaInventarioCreate
from osiris.modules.inventario.movimientos.services.movimiento_inventario_service import MovimientoInventarioService
from osiris.modules.inventario.producto.entity import Producto
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente


def _build_test_engine():
    # Algunos tests unitarios limpian SQLModel.metadata durante la colección.
    # Re-registramos tablas requeridas para resolver FKs por nombre.
    for table in (
        TipoContribuyente.__table__,
        Empresa.__table__,
        Sucursal.__table__,
        Bodega.__table__,
        CasaComercial.__table__,
        Producto.__table__,
        AuditLog.__table__,
        MovimientoInventario.__table__,
        MovimientoInventarioDetalle.__table__,
        InventarioStock.__table__,
    ):
        if table.key not in SQLModel.metadata.tables:
            SQLModel.metadata._add_table(table.name, table.schema, table)  # type: ignore[attr-defined]

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
            AuditLog.__table__,
            # Tablas nuevas
            MovimientoInventario.__table__,
            MovimientoInventarioDetalle.__table__,
            InventarioStock.__table__,
        ],
    )
    return engine


def test_crear_movimiento_borrador():
    engine = _build_test_engine()
    service = MovimientoInventarioService()

    with Session(engine) as session:
        tipo_contribuyente = TipoContribuyente(codigo="01", nombre="SOCIEDAD", activo=True)
        session.add(tipo_contribuyente)

        empresa = Empresa(
            razon_social="Empresa Inventario",
            nombre_comercial="Empresa Inventario",
            ruc="1790012345001",
            direccion_matriz="Av. Quito",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(empresa)
        session.flush()

        bodega = Bodega(
            codigo_bodega="BOD-001",
            nombre_bodega="Bodega Principal",
            empresa_id=empresa.id,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(bodega)

        producto = Producto(
            nombre="Producto Kardex",
            tipo="BIEN",
            pvp=Decimal("10.00"),
            cantidad=25,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(producto)
        session.commit()
        session.refresh(bodega)
        session.refresh(producto)

        payload = MovimientoInventarioCreate(
            bodega_id=bodega.id,
            tipo_movimiento=TipoMovimientoInventario.EGRESO,
            referencia_documento="FAC-00001",
            usuario_auditoria="tester",
            detalles=[
                {
                    "producto_id": producto.id,
                    "cantidad": Decimal("2.00"),
                    "costo_unitario": Decimal("5.25"),
                }
            ],
        )

        movimiento = service.crear_movimiento_borrador(session, payload)
        session.refresh(producto)

        detalles = session.exec(
            select(MovimientoInventarioDetalle).where(
                MovimientoInventarioDetalle.movimiento_inventario_id == movimiento.id
            )
        ).all()

        assert movimiento.estado == EstadoMovimientoInventario.BORRADOR
        assert len(detalles) == 1
        assert detalles[0].cantidad == Decimal("2.00")
        # Criterio E3-1: crear BORRADOR no altera stock.
        assert producto.cantidad == 25


@pytest.mark.parametrize("cantidad", [Decimal("0"), Decimal("-1")])
def test_validacion_cantidades_negativas(cantidad: Decimal):
    with pytest.raises(ValidationError):
        MovimientoInventarioCreate(
            bodega_id="11111111-1111-1111-1111-111111111111",
            tipo_movimiento=TipoMovimientoInventario.INGRESO,
            referencia_documento="DOC-TEST",
            detalles=[
                {
                    "producto_id": "22222222-2222-2222-2222-222222222222",
                    "cantidad": cantidad,
                    "costo_unitario": Decimal("1.00"),
                }
            ],
        )


def test_concurrencia_stock_negativo(tmp_path):
    db_file = tmp_path / "inventario_stock_concurrencia.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
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
            AuditLog.__table__,
            MovimientoInventario.__table__,
            MovimientoInventarioDetalle.__table__,
            InventarioStock.__table__,
        ],
    )

    service = MovimientoInventarioService()
    with Session(engine) as session:
        tipo_contribuyente = TipoContribuyente(codigo="01", nombre="SOCIEDAD", activo=True)
        session.add(tipo_contribuyente)

        empresa = Empresa(
            razon_social="Empresa Concurrencia",
            nombre_comercial="Empresa Concurrencia",
            ruc="1790012345001",
            direccion_matriz="Av. Quito",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(empresa)
        session.flush()

        bodega = Bodega(
            codigo_bodega="BOD-002",
            nombre_bodega="Bodega Concurrencia",
            empresa_id=empresa.id,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(bodega)

        producto = Producto(
            nombre="Producto Concurrencia",
            tipo="BIEN",
            pvp=Decimal("10.00"),
            cantidad=15,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(producto)
        session.flush()

        stock = InventarioStock(
            bodega_id=bodega.id,
            producto_id=producto.id,
            cantidad_actual=Decimal("15.0000"),
            costo_promedio_vigente=Decimal("2.0000"),
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(stock)
        session.commit()
        bodega_id = bodega.id
        producto_id = producto.id

        movimiento_ids = []
        for i in range(5):
            payload = MovimientoInventarioCreate(
                bodega_id=bodega_id,
                tipo_movimiento=TipoMovimientoInventario.EGRESO,
                referencia_documento=f"EGR-CONC-{i}",
                usuario_auditoria="tester",
                detalles=[
                    {
                        "producto_id": producto_id,
                        "cantidad": Decimal("10.0000"),
                        "costo_unitario": Decimal("2.0000"),
                    }
                ],
            )
            movimiento = service.crear_movimiento_borrador(session, payload)
            movimiento_ids.append(movimiento.id)

    def _worker_confirmar(movimiento_id):
        with Session(engine) as worker_session:
            worker_service = MovimientoInventarioService()
            try:
                worker_service.confirmar_movimiento(worker_session, movimiento_id)
                return "ok"
            except ValueError:
                return "error"

    with ThreadPoolExecutor(max_workers=5) as executor:
        resultados = list(executor.map(_worker_confirmar, movimiento_ids))

    assert resultados.count("ok") == 1
    assert resultados.count("error") == 4

    with Session(engine) as session:
        stmt = select(InventarioStock).where(
            InventarioStock.bodega_id == bodega_id,
            InventarioStock.producto_id == producto_id,
            InventarioStock.activo.is_(True),
        )
        stock_final = session.exec(stmt).one()
        assert stock_final.cantidad_actual == Decimal("5.0000")


def test_calculo_promedio_ponderado():
    engine = _build_test_engine()
    service = MovimientoInventarioService()

    with Session(engine) as session:
        tipo_contribuyente = TipoContribuyente(codigo="01", nombre="SOCIEDAD", activo=True)
        session.add(tipo_contribuyente)

        empresa = Empresa(
            razon_social="Empresa Promedio",
            nombre_comercial="Empresa Promedio",
            ruc="1790012345001",
            direccion_matriz="Av. Quito",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(empresa)
        session.flush()

        bodega = Bodega(
            codigo_bodega="BOD-003",
            nombre_bodega="Bodega Promedio",
            empresa_id=empresa.id,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(bodega)

        producto = Producto(
            nombre="Producto Promedio",
            tipo="BIEN",
            pvp=Decimal("10.00"),
            cantidad=0,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(producto)
        session.commit()
        session.refresh(bodega)
        session.refresh(producto)

        payload_1 = MovimientoInventarioCreate(
            bodega_id=bodega.id,
            tipo_movimiento=TipoMovimientoInventario.INGRESO,
            referencia_documento="ING-1",
            usuario_auditoria="tester",
            detalles=[
                {
                    "producto_id": producto.id,
                    "cantidad": Decimal("10.0000"),
                    "costo_unitario": Decimal("10.0000"),
                }
            ],
        )
        mov_1 = service.crear_movimiento_borrador(session, payload_1)
        service.confirmar_movimiento(session, mov_1.id)

        payload_2 = MovimientoInventarioCreate(
            bodega_id=bodega.id,
            tipo_movimiento=TipoMovimientoInventario.INGRESO,
            referencia_documento="ING-2",
            usuario_auditoria="tester",
            detalles=[
                {
                    "producto_id": producto.id,
                    "cantidad": Decimal("10.0000"),
                    "costo_unitario": Decimal("20.0000"),
                }
            ],
        )
        mov_2 = service.crear_movimiento_borrador(session, payload_2)
        service.confirmar_movimiento(session, mov_2.id)

        stmt = select(InventarioStock).where(
            InventarioStock.bodega_id == bodega.id,
            InventarioStock.producto_id == producto.id,
            InventarioStock.activo.is_(True),
        )
        stock = session.exec(stmt).one()
        assert stock.cantidad_actual == Decimal("20.0000")
        assert stock.costo_promedio_vigente == Decimal("15.0000")


def test_egreso_congela_costo():
    engine = _build_test_engine()
    service = MovimientoInventarioService()

    with Session(engine) as session:
        tipo_contribuyente = TipoContribuyente(codigo="01", nombre="SOCIEDAD", activo=True)
        session.add(tipo_contribuyente)

        empresa = Empresa(
            razon_social="Empresa Egreso",
            nombre_comercial="Empresa Egreso",
            ruc="1790012345001",
            direccion_matriz="Av. Quito",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(empresa)
        session.flush()

        bodega = Bodega(
            codigo_bodega="BOD-004",
            nombre_bodega="Bodega Egreso",
            empresa_id=empresa.id,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(bodega)

        producto = Producto(
            nombre="Producto Egreso",
            tipo="BIEN",
            pvp=Decimal("10.00"),
            cantidad=0,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(producto)
        session.flush()

        stock = InventarioStock(
            bodega_id=bodega.id,
            producto_id=producto.id,
            cantidad_actual=Decimal("30.0000"),
            costo_promedio_vigente=Decimal("7.3456"),
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(stock)
        session.commit()
        session.refresh(bodega)
        session.refresh(producto)

        payload = MovimientoInventarioCreate(
            bodega_id=bodega.id,
            tipo_movimiento=TipoMovimientoInventario.EGRESO,
            referencia_documento="EGR-1",
            usuario_auditoria="tester",
            detalles=[
                {
                    "producto_id": producto.id,
                    "cantidad": Decimal("5.0000"),
                    "costo_unitario": Decimal("99.9999"),
                }
            ],
        )
        movimiento = service.crear_movimiento_borrador(session, payload)
        service.confirmar_movimiento(session, movimiento.id)

        detalle = (
            session.exec(
                select(MovimientoInventarioDetalle).where(
                    MovimientoInventarioDetalle.movimiento_inventario_id == movimiento.id
                )
            )
            .all()[0]
        )
        stmt = select(InventarioStock).where(
            InventarioStock.bodega_id == bodega.id,
            InventarioStock.producto_id == producto.id,
            InventarioStock.activo.is_(True),
        )
        stock_actualizado = session.exec(stmt).one()
        assert detalle.costo_unitario == Decimal("7.3456")
        assert stock_actualizado.costo_promedio_vigente == Decimal("7.3456")
        assert stock_actualizado.cantidad_actual == Decimal("25.0000")


def test_transferencia_entre_bodegas_actualiza_stock_origen_destino():
    engine = _build_test_engine()
    service = MovimientoInventarioService()

    with Session(engine) as session:
        tipo_contribuyente = TipoContribuyente(codigo="01", nombre="SOCIEDAD", activo=True)
        session.add(tipo_contribuyente)

        empresa = Empresa(
            razon_social="Empresa Transferencia",
            nombre_comercial="Empresa Transferencia",
            ruc="1790012345001",
            direccion_matriz="Av. Quito",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(empresa)
        session.flush()

        bodega_origen = Bodega(
            codigo_bodega="BOD-ORIGEN",
            nombre_bodega="Bodega Origen",
            empresa_id=empresa.id,
            usuario_auditoria="tester",
            activo=True,
        )
        bodega_destino = Bodega(
            codigo_bodega="BOD-DESTINO",
            nombre_bodega="Bodega Destino",
            empresa_id=empresa.id,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(bodega_origen)
        session.add(bodega_destino)

        producto = Producto(
            nombre="Producto Transferencia",
            tipo="BIEN",
            pvp=Decimal("10.00"),
            cantidad=Decimal("30.0000"),
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(producto)
        session.flush()

        stock_origen = InventarioStock(
            bodega_id=bodega_origen.id,
            producto_id=producto.id,
            cantidad_actual=Decimal("30.0000"),
            costo_promedio_vigente=Decimal("4.5000"),
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(stock_origen)
        session.commit()

        result = service.transferir_entre_bodegas(
            session,
            payload=TransferenciaInventarioCreate(
                bodega_origen_id=bodega_origen.id,
                bodega_destino_id=bodega_destino.id,
                referencia_documento="TRF-001",
                usuario_auditoria="tester",
                detalles=[
                    {
                        "producto_id": producto.id,
                        "cantidad": Decimal("10.0000"),
                    }
                ],
            ),
        )
        assert result.bodega_origen_id == bodega_origen.id
        assert result.bodega_destino_id == bodega_destino.id

        stock_origen_post = session.exec(
            select(InventarioStock).where(
                InventarioStock.bodega_id == bodega_origen.id,
                InventarioStock.producto_id == producto.id,
            )
        ).one()
        stock_destino_post = session.exec(
            select(InventarioStock).where(
                InventarioStock.bodega_id == bodega_destino.id,
                InventarioStock.producto_id == producto.id,
            )
        ).one()
        assert stock_origen_post.cantidad_actual == Decimal("20.0000")
        assert stock_destino_post.cantidad_actual == Decimal("10.0000")


def test_anular_movimiento_confirmado_reversa_stock():
    engine = _build_test_engine()
    service = MovimientoInventarioService()

    with Session(engine) as session:
        tipo_contribuyente = TipoContribuyente(codigo="01", nombre="SOCIEDAD", activo=True)
        session.add(tipo_contribuyente)
        empresa = Empresa(
            razon_social="Empresa Anulacion Mov",
            nombre_comercial="Empresa Anulacion Mov",
            ruc="1790012345001",
            direccion_matriz="Av. Quito",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(empresa)
        session.flush()
        bodega = Bodega(
            codigo_bodega="BOD-ANUL-1",
            nombre_bodega="Bodega Anulacion",
            empresa_id=empresa.id,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(bodega)
        producto = Producto(
            nombre="Producto Anulacion Mov",
            tipo="BIEN",
            pvp=Decimal("10.00"),
            cantidad=Decimal("0.0000"),
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(producto)
        session.commit()

        movimiento = service.crear_movimiento_borrador(
            session,
            MovimientoInventarioCreate(
                bodega_id=bodega.id,
                tipo_movimiento=TipoMovimientoInventario.INGRESO,
                referencia_documento="ING-ANUL-1",
                usuario_auditoria="tester",
                detalles=[
                    {
                        "producto_id": producto.id,
                        "cantidad": Decimal("8.0000"),
                        "costo_unitario": Decimal("3.0000"),
                    }
                ],
            ),
        )
        service.confirmar_movimiento(session, movimiento.id)

        stock_post_ingreso = session.exec(
            select(InventarioStock).where(
                InventarioStock.bodega_id == bodega.id,
                InventarioStock.producto_id == producto.id,
            )
        ).one()
        assert stock_post_ingreso.cantidad_actual == Decimal("8.0000")

        anulado = service.anular_movimiento(
            session,
            movimiento.id,
            motivo="Error de digitación",
            usuario_autorizador="tester",
        )
        assert anulado.estado == EstadoMovimientoInventario.ANULADO

        stock_post_anulacion = session.exec(
            select(InventarioStock).where(
                InventarioStock.bodega_id == bodega.id,
                InventarioStock.producto_id == producto.id,
            )
        ).one()
        assert stock_post_anulacion.cantidad_actual == Decimal("0.0000")
