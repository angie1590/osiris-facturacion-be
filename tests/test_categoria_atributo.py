"""
Tests unitarios para CategoriaAtributo
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.categoria_atributo.service import CategoriaAtributoService
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.categoria_atributo.models import (
    CategoriaAtributoCreate,
    CategoriaAtributoUpdate,
)
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria, TipoProducto
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AuditLog.__table__,
            CasaComercial.__table__,
            Categoria.__table__,
            Atributo.__table__,
            CategoriaAtributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoAtributoValor.__table__,
        ],
    )
    return engine


def test_categoria_atributo_service_create_ok():
    """Verificar que create instancia y persiste la asociación"""
    session = MagicMock()
    service = CategoriaAtributoService()

    categoria_id = uuid4()
    atributo_id = uuid4()

    dto = CategoriaAtributoCreate(
        categoria_id=categoria_id,
        atributo_id=atributo_id,
        orden=1,
        obligatorio=True,
    )

    # Mock de session.add / commit / refresh
    created_entity = CategoriaAtributo(
        categoria_id=categoria_id,
        atributo_id=atributo_id,
        orden=1,
        obligatorio=True,
        usuario_auditoria="api",
        activo=True,
    )
    created_entity.id = uuid4()

    def mock_refresh(entity):
        entity.id = created_entity.id

    session.refresh.side_effect = mock_refresh

    service.create(session, dto, usuario_auditoria="test_user")

    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once()


def test_categoria_atributo_service_create_inyecta_default_seguro_integer_obligatorio():
    session = MagicMock()
    service = CategoriaAtributoService()

    categoria_id = uuid4()
    atributo_id = uuid4()
    atributo_master = Atributo(
        nombre="Edad mínima",
        tipo_dato=TipoDato.INTEGER,
        usuario_auditoria="test",
        activo=True,
    )
    atributo_master.id = atributo_id
    session.get.return_value = atributo_master

    dto = CategoriaAtributoCreate(
        categoria_id=categoria_id,
        atributo_id=atributo_id,
        obligatorio=True,
        valor_default=None,
    )

    service.create(session, dto, usuario_auditoria="test_user")

    session.add.assert_called_once()
    created_entity = session.add.call_args[0][0]
    assert isinstance(created_entity, CategoriaAtributo)
    assert created_entity.valor_default == "0"
    session.commit.assert_called_once()
    session.refresh.assert_called_once()


def test_categoria_atributo_service_update_ok():
    """Verificar que update modifica campos permitidos"""
    session = MagicMock()
    service = CategoriaAtributoService()

    entity_id = uuid4()
    existing = CategoriaAtributo(
        categoria_id=uuid4(),
        atributo_id=uuid4(),
        orden=1,
        obligatorio=False,
        usuario_auditoria="original",
        activo=True,
    )
    existing.id = entity_id

    session.get.return_value = existing

    dto = CategoriaAtributoUpdate(orden=5, obligatorio=True)

    result = service.update(session, entity_id, dto, usuario_auditoria="test_user")

    assert result is not None
    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once()


def test_categoria_atributo_service_update_not_found():
    """Verificar que update devuelve None si no existe"""
    session = MagicMock()
    service = CategoriaAtributoService()

    session.get.return_value = None

    dto = CategoriaAtributoUpdate(orden=10)

    result = service.update(session, uuid4(), dto)

    assert result is None
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_categoria_atributo_service_delete_soft():
    """Verificar que delete hace soft-delete (activo=False)"""
    session = MagicMock()
    service = CategoriaAtributoService()

    entity_id = uuid4()
    existing = CategoriaAtributo(
        categoria_id=uuid4(),
        atributo_id=uuid4(),
        orden=1,
        obligatorio=False,
        usuario_auditoria="original",
        activo=True,
    )
    existing.id = entity_id

    session.get.return_value = existing

    result = service.delete(session, entity_id, usuario_auditoria="test_user")

    assert result is True
    assert existing.activo is False
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_categoria_atributo_service_delete_not_found():
    """Verificar que delete devuelve False si no existe"""
    session = MagicMock()
    service = CategoriaAtributoService()

    session.get.return_value = None

    result = service.delete(session, uuid4())

    assert result is False
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_categoria_atributo_service_list_paginated():
    """Verificar que list_paginated respeta filtros y paginación"""
    session = MagicMock()
    service = CategoriaAtributoService()

    categoria_id = uuid4()

    mock_exec = MagicMock()
    mock_exec.return_value = [
        CategoriaAtributo(
            categoria_id=categoria_id,
            atributo_id=uuid4(),
            orden=1,
            obligatorio=True,
            usuario_auditoria="api",
            activo=True,
        )
    ]
    session.exec = mock_exec

    result = service.list_paginated(session, skip=0, limit=10, categoria_id=categoria_id)

    assert len(result) == 1
    session.exec.assert_called_once()


def test_categoria_atributo_backfill_idempotente_respeta_valor_existente():
    engine = _build_test_engine()
    service = CategoriaAtributoService()

    with Session(engine) as session:
        categoria = Categoria(
            nombre="Categoria A",
            es_padre=False,
            activo=True,
            usuario_auditoria="test",
        )
        atributo = Atributo(
            nombre=f"Color-{uuid4().hex[:8]}",
            tipo_dato=TipoDato.STRING,
            activo=True,
            usuario_auditoria="test",
        )
        producto_1 = Producto(
            nombre=f"Producto-1-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            activo=True,
            usuario_auditoria="test",
        )
        producto_2 = Producto(
            nombre=f"Producto-2-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("11.00"),
            activo=True,
            usuario_auditoria="test",
        )
        session.add(categoria)
        session.add(atributo)
        session.add(producto_1)
        session.add(producto_2)
        session.commit()
        session.refresh(categoria)
        session.refresh(atributo)
        session.refresh(producto_1)
        session.refresh(producto_2)

        session.add(
            ProductoCategoria(
                producto_id=producto_1.id,
                categoria_id=categoria.id,
            )
        )
        session.add(
            ProductoCategoria(
                producto_id=producto_2.id,
                categoria_id=categoria.id,
            )
        )
        session.commit()

        session.add(
            ProductoAtributoValor(
                producto_id=producto_1.id,
                atributo_id=atributo.id,
                valor_string="Rojo",
                activo=True,
                usuario_auditoria="test",
            )
        )
        session.commit()

        dto = CategoriaAtributoCreate(
            categoria_id=categoria.id,
            atributo_id=atributo.id,
            obligatorio=True,
            valor_default="Negro",
        )
        created = service.create(session, dto, usuario_auditoria="test")
        assert created.valor_default == "Negro"

        rows = session.exec(
            select(ProductoAtributoValor).where(ProductoAtributoValor.atributo_id == atributo.id)
        ).all()

        assert len(rows) == 2
        rows_por_producto = {row.producto_id: row for row in rows}
        assert rows_por_producto[producto_1.id].valor_string == "Rojo"
        assert rows_por_producto[producto_2.id].valor_string == "Negro"
