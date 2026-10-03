from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria, TipoProducto
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor


def _engine():
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
            Atributo.__table__,
            Categoria.__table__,
            CategoriaAtributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoAtributoValor.__table__,
        ],
    )
    return engine


def _seed_collision(session: Session):
    old_parent = Categoria(nombre="Origen", es_padre=True, usuario_auditoria="test", activo=True)
    destination = Categoria(nombre="Destino", es_padre=True, usuario_auditoria="test", activo=True)
    moving = Categoria(nombre="Subrama", es_padre=False, usuario_auditoria="test", activo=True)
    session.add_all([old_parent, destination, moving])
    session.flush()
    moving.parent_id = old_parent.id
    source_attribute = Atributo(nombre="Color", tipo_dato=TipoDato.STRING, usuario_auditoria="test", activo=True)
    inherited_attribute = Atributo(nombre="color", tipo_dato=TipoDato.STRING, usuario_auditoria="test", activo=True)
    product = Producto(nombre=f"P-{uuid4().hex[:6]}", tipo=TipoProducto.BIEN, pvp=Decimal("10.00"), usuario_auditoria="test", activo=True)
    session.add_all([source_attribute, inherited_attribute, product])
    session.flush()
    session.add_all(
        [
            CategoriaAtributo(categoria_id=moving.id, atributo_id=source_attribute.id, usuario_auditoria="test", activo=True),
            CategoriaAtributo(categoria_id=destination.id, atributo_id=inherited_attribute.id, usuario_auditoria="test", activo=True),
            ProductoCategoria(producto_id=product.id, categoria_id=moving.id),
            ProductoAtributoValor(producto_id=product.id, atributo_id=inherited_attribute.id, valor_string="Azul", usuario_auditoria="test", activo=True),
            ProductoAtributoValor(producto_id=product.id, atributo_id=source_attribute.id, valor_string="Rojo", usuario_auditoria="test", activo=True),
        ]
    )
    session.commit()
    return old_parent, destination, moving, product, source_attribute, inherited_attribute


def test_category_move_requires_confirmation_and_clears_only_displaced_collision_values():
    engine = _engine()
    with Session(engine) as session:
        _old_parent, destination, moving, product, source_attribute, inherited_attribute = _seed_collision(session)
        service = CategoriaService()

        with pytest.raises(HTTPException) as exc_info:
            service.update(session, moving.id, {"parent_id": destination.id})

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "CATEGORY_ATTRIBUTE_COLLISION_REQUIRES_CONFIRMATION"
        session.refresh(moving)
        assert moving.parent_id == _old_parent.id

        updated = service.update(
            session,
            moving.id,
            {"parent_id": destination.id, "confirmar_limpieza_colision": True},
        )
        assert updated.parent_id == destination.id

        values = session.exec(
            select(ProductoAtributoValor)
            .where(ProductoAtributoValor.producto_id == product.id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).all()
        by_attribute = {value.atributo_id: value for value in values}
        assert by_attribute[inherited_attribute.id].activo is False
        assert by_attribute[inherited_attribute.id].valor_string == "Azul"
        assert by_attribute[source_attribute.id].activo is True
        assert by_attribute[source_attribute.id].valor_string == "Rojo"

        audit = session.exec(
            select(AuditLog).where(AuditLog.accion == "MOVE_CATEGORY_CLEAR_ATTRIBUTE_COLLISION")
        ).first()
        assert audit is not None
        assert audit.estado_nuevo["removed_values"][0]["producto_id"] == str(product.id)