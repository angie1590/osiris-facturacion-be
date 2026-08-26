from __future__ import annotations

import pytest
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.cliente.entity import Cliente
from osiris.modules.common.empleado.entity import Empleado
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.punto_emision.entity import PuntoEmision, PuntoEmisionSecuencial
from osiris.modules.common.proveedor_persona.entity import ProveedorPersona
from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.common.tipo_cliente.entity import TipoCliente
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.sri.core_sri.models import (
    Compra,
    CompraDetalle,
    CompraDetalleImpuesto,
    CuentaPorCobrar,
    CuentaPorPagar,
    DocumentoElectronico,
    DocumentoElectronicoHistorial,
    DocumentoSriCola,
    PagoCxC,
    PagoCxP,
    RetencionRecibida,
    RetencionRecibidaDetalle,
    Venta,
    VentaDetalle,
    VentaDetalleImpuesto,
)
from osiris.modules.inventario.movimientos.models import (
    InventarioStock,
    MovimientoInventario,
    MovimientoInventarioDetalle,
)
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.atributo.entity import Atributo
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoBodega,
    ProductoCategoria,
    ProductoImpuesto,
    ProductoProveedorPersona,
    ProductoProveedorSociedad,
)
from osiris.modules.sri.impuesto_catalogo.entity import AplicaA, ImpuestoCatalogo, TipoImpuesto
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente


def _restore_metadata_tables(tables: list) -> None:
    # Algunos tests limpian SQLModel.metadata durante colección; reinyectamos tablas requeridas.
    for table in tables:
        if table.key not in SQLModel.metadata.tables:
            SQLModel.metadata._add_table(table.name, table.schema, table)  # type: ignore[attr-defined]


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    required_tables = [
        TipoContribuyente.__table__,
        AuditLog.__table__,
        Empresa.__table__,
        Sucursal.__table__,
        PuntoEmision.__table__,
        PuntoEmisionSecuencial.__table__,
        Bodega.__table__,
        Categoria.__table__,
        CasaComercial.__table__,
        ImpuestoCatalogo.__table__,
        Producto.__table__,
        ProductoCategoria.__table__,
        ProductoProveedorPersona.__table__,
        ProductoProveedorSociedad.__table__,
        ProductoImpuesto.__table__,
        ProductoBodega.__table__,
        Persona.__table__,
        TipoCliente.__table__,
        Cliente.__table__,
        Empleado.__table__,
        Rol.__table__,
        Usuario.__table__,
        ProveedorPersona.__table__,
        ProveedorSociedad.__table__,
        Atributo.__table__,
        CategoriaAtributo.__table__,
        MovimientoInventario.__table__,
        MovimientoInventarioDetalle.__table__,
        InventarioStock.__table__,
        Venta.__table__,
        VentaDetalle.__table__,
        VentaDetalleImpuesto.__table__,
        Compra.__table__,
        CompraDetalle.__table__,
        CompraDetalleImpuesto.__table__,
        CuentaPorPagar.__table__,
        PagoCxP.__table__,
        CuentaPorCobrar.__table__,
        PagoCxC.__table__,
        RetencionRecibida.__table__,
        RetencionRecibidaDetalle.__table__,
        DocumentoElectronico.__table__,
        DocumentoElectronicoHistorial.__table__,
        DocumentoSriCola.__table__,
    ]
    _restore_metadata_tables(required_tables)
    SQLModel.metadata.create_all(engine, tables=required_tables)
    with Session(engine) as session:
        tipos_seed = [
            ("01", "Persona Natural"),
            ("02", "Sociedad"),
            ("03", "RIMPE – Negocio Popular"),
            ("04", "RIMPE – Emprendedor"),
            ("05", "Gran Contribuyente"),
        ]
        for codigo, nombre in tipos_seed:
            tipo = session.get(TipoContribuyente, codigo)
            if tipo is None:
                session.add(TipoContribuyente(codigo=codigo, nombre=nombre, activo=True))
        iva = session.exec(
            select(ImpuestoCatalogo).where(
                ImpuestoCatalogo.tipo_impuesto == TipoImpuesto.IVA,
                ImpuestoCatalogo.codigo_sri == "2",
                ImpuestoCatalogo.activo.is_(True),
            )
        ).first()
        if iva is None:
            session.add(
                ImpuestoCatalogo(
                    tipo_impuesto=TipoImpuesto.IVA,
                    codigo_tipo_impuesto="2",
                    codigo_sri="2",
                    descripcion="IVA 0%",
                    vigente_desde=date.today(),
                    aplica_a=AplicaA.AMBOS,
                    porcentaje_iva=Decimal("0.00"),
                    usuario_auditoria="smoke",
                    activo=True,
                )
            )
        session.commit()
    return engine


@pytest.fixture(scope="session")
def client(test_engine):
    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.state.security_audit_engine = test_engine
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def db_session(test_engine):
    with Session(test_engine) as session:
        yield session
