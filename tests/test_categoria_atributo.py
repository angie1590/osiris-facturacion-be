"""
Tests unitarios para CategoriaAtributo
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo, CatalogoValor
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.inventario.categoria_atributo.service import (
    CategoriaAtributoService,
)
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.categoria_atributo.models import (
    CategoriaAtributoCreate,
    CategoriaAtributoUpdate,
)
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoCategoria,
    TipoProducto,
)
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeo,
    ProductoAtributoValor,
)


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
            Catalogo.__table__,
            CatalogoValor.__table__,
            CasaComercial.__table__,
            Unidad.__table__,
            Categoria.__table__,
            Atributo.__table__,
            CategoriaAtributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoAtributoValor.__table__,
            ProductoAtributoRemapeo.__table__,
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


def test_categoria_atributo_service_create_no_inventa_default_para_obligatorio():
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
    assert created_entity.valor_default is None
    session.commit.assert_called_once()
    session.refresh.assert_called_once()


def test_required_mapping_without_default_is_valid_when_no_products_are_missing():
    engine = _build_test_engine()
    with Session(engine) as session:
        category = Categoria(nombre="Consolas", activo=True)
        attribute = Atributo(
            nombre="Edición", tipo_dato=TipoDato.STRING, activo=True
        )
        session.add_all([category, attribute])
        session.commit()

        mapping = CategoriaAtributoService().create(
            session,
            CategoriaAtributoCreate(
                categoria_id=category.id,
                atributo_id=attribute.id,
                obligatorio=True,
            ),
        )

        assert mapping.obligatorio is True
        assert mapping.valor_default is None
        assert session.exec(select(ProductoAtributoValor)).all() == []
    engine.dispose()


def test_optional_default_is_validated_against_attribute_bounds():
    engine = _build_test_engine()
    service = CategoriaAtributoService()
    with Session(engine) as session:
        category = Categoria(nombre="Cámaras", activo=True)
        attribute = Atributo(
            nombre="Zoom",
            tipo_dato=TipoDato.INTEGER,
            min_value=1,
            max_value=10,
            activo=True,
        )
        session.add_all([category, attribute])
        session.commit()

        with pytest.raises(HTTPException) as error:
            service.create(
                session,
                CategoriaAtributoCreate(
                    categoria_id=category.id,
                    atributo_id=attribute.id,
                    obligatorio=False,
                    valor_default="11",
                ),
            )

        assert error.value.status_code == 422
        assert error.value.detail["code"] == "DEFAULT_VALUE_INVALID"
        assert session.exec(select(CategoriaAtributo)).all() == []
    engine.dispose()


def test_select_default_is_canonicalized_even_when_optional():
    engine = _build_test_engine()
    with Session(engine) as session:
        category = Categoria(nombre="Ropa", activo=True)
        attribute = Atributo(
            nombre="Color",
            tipo_dato=TipoDato.SELECT,
            select_options=["Rojo", "Azul"],
            activo=True,
        )
        session.add_all([category, attribute])
        session.commit()

        created = CategoriaAtributoService().create(
            session,
            CategoriaAtributoCreate(
                categoria_id=category.id,
                atributo_id=attribute.id,
                obligatorio=False,
                valor_default="rojo",
            ),
        )

        assert created.valor_default == "Rojo"
    engine.dispose()


def test_catalog_default_requires_an_active_catalog_value():
    engine = _build_test_engine()
    with Session(engine) as session:
        category = Categoria(nombre="Textiles", activo=True)
        catalog = Catalogo(nombre="Materiales", activo=True)
        session.add_all([category, catalog])
        session.flush()
        session.add(
            CatalogoValor(
                catalogo_id=catalog.id,
                valor="Algodón",
                activo=True,
            )
        )
        attribute = Atributo(
            nombre="Tela",
            tipo_dato=TipoDato.CATALOG,
            catalog_id=catalog.id,
            activo=True,
        )
        session.add(attribute)
        session.commit()

        created = CategoriaAtributoService().create(
            session,
            CategoriaAtributoCreate(
                categoria_id=category.id,
                atributo_id=attribute.id,
                obligatorio=False,
                valor_default="Algodón",
            ),
        )
        assert created.valor_default == "Algodón"

        with pytest.raises(HTTPException) as error:
            CategoriaAtributoService().update(
                session,
                created.id,
                CategoriaAtributoUpdate(valor_default="Lino"),
            )
        assert error.value.detail["code"] == "DEFAULT_VALUE_INVALID"
    engine.dispose()


def test_update_distinguishes_omitted_and_explicit_null_for_default_and_order():
    engine = _build_test_engine()
    with Session(engine) as session:
        category = Categoria(nombre="Audio", activo=True)
        attribute = Atributo(
            nombre="Canales", tipo_dato=TipoDato.INTEGER, activo=True
        )
        session.add_all([category, attribute])
        session.flush()
        mapping = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            orden=4,
            obligatorio=False,
            valor_default="2",
            activo=True,
        )
        session.add(mapping)
        session.commit()

        service = CategoriaAtributoService()
        unchanged = service.update(
            session, mapping.id, CategoriaAtributoUpdate()
        )
        assert unchanged is not None
        assert unchanged.orden == 4
        assert unchanged.valor_default == "2"

        cleared = service.update(
            session,
            mapping.id,
            CategoriaAtributoUpdate(orden=None, valor_default=None),
        )
        assert cleared is not None
        assert cleared.orden is None
        assert cleared.valor_default is None
    engine.dispose()


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

    result = service.list_paginated(
        session, skip=0, limit=10, categoria_id=categoria_id
    )

    assert len(result) == 1
    session.exec.assert_called_once()


@pytest.mark.parametrize(
    ("required", "apply_default", "expected_rows"),
    [
        (True, False, 1),
        (True, True, 2),
        (False, False, 1),
        (False, True, 2),
    ],
)
def test_categoria_atributo_create_backfill_requires_explicit_opt_in(
    required: bool, apply_default: bool, expected_rows: int
):
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
            obligatorio=required,
            valor_default="Negro",
            aplicar_default_a_existentes=apply_default,
        )
        if required and not apply_default:
            with pytest.raises(HTTPException) as error:
                service.create(session, dto, usuario_auditoria="test")
            assert error.value.status_code == 409
            assert error.value.detail["code"] == "PRODUCT_REQUIRED_ATTRIBUTES_MISSING"
            assert session.exec(select(CategoriaAtributo)).all() == []
        else:
            created = service.create(session, dto, usuario_auditoria="test")
            assert created.valor_default == "Negro"

        rows = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.atributo_id == atributo.id
            )
        ).all()

        assert len(rows) == expected_rows
        rows_por_producto = {row.producto_id: row for row in rows}
        assert rows_por_producto[producto_1.id].valor_string == "Rojo"
        if apply_default:
            assert rows_por_producto[producto_2.id].valor_string == "Negro"
        else:
            assert producto_2.id not in rows_por_producto


def test_required_attribute_impact_reports_only_products_without_valid_eav():
    engine = _build_test_engine()
    service = CategoriaAtributoService()
    with Session(engine) as session:
        category = Categoria(nombre="Cámaras", activo=True)
        attribute = Atributo(
            nombre="Sensor", tipo_dato=TipoDato.STRING, activo=True
        )
        products = [
            Producto(
                nombre=f"Cámara {index}-{uuid4().hex[:6]}",
                tipo=TipoProducto.BIEN,
                pvp=Decimal("20.00"),
                activo=True,
                usuario_auditoria="test",
            )
            for index in range(2)
        ]
        session.add_all([category, attribute, *products])
        session.flush()
        mapping = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            obligatorio=False,
            valor_default=None,
            activo=True,
        )
        session.add(mapping)
        session.add_all(
            ProductoCategoria(producto_id=product.id, categoria_id=category.id)
            for product in products
        )
        session.add(
            ProductoAtributoValor(
                producto_id=products[0].id,
                atributo_id=attribute.id,
                valor_string="CMOS",
                activo=True,
                usuario_auditoria="test",
            )
        )
        session.commit()

        state, affected, missing, names = service.required_attribute_impact(
            session, mapping
        )

    assert set(affected) == {product.id for product in products}
    assert missing == [products[1].id]
    assert names[products[1].id] == products[1].nombre
    assert state["mapping"]["id"] == str(mapping.id)
    engine.dispose()


def test_proposed_local_override_respects_more_specific_descendant_mapping():
    engine = _build_test_engine()
    service = CategoriaAtributoService()
    with Session(engine) as session:
        root = Categoria(nombre="Electrónica", activo=True)
        target = Categoria(nombre="Computadores", parent_id=root.id, activo=True)
        deeper = Categoria(nombre="Gaming", parent_id=target.id, activo=True)
        attribute = Atributo(
            nombre="Memoria", tipo_dato=TipoDato.INTEGER, activo=True
        )
        target_product = Producto(
            nombre=f"Laptop-{uuid4().hex[:6]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            activo=True,
        )
        deeper_product = Producto(
            nombre=f"Gaming-{uuid4().hex[:6]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            activo=True,
        )
        session.add_all(
            [root, target, deeper, attribute, target_product, deeper_product]
        )
        session.flush()
        target.parent_id = root.id
        deeper.parent_id = target.id
        root_mapping = CategoriaAtributo(
            categoria_id=root.id, atributo_id=attribute.id, obligatorio=False, activo=True
        )
        deeper_mapping = CategoriaAtributo(
            categoria_id=deeper.id,
            atributo_id=attribute.id,
            obligatorio=False,
            activo=True,
        )
        session.add_all(
            [
                root_mapping,
                deeper_mapping,
                ProductoCategoria(producto_id=target_product.id, categoria_id=target.id),
                ProductoCategoria(producto_id=deeper_product.id, categoria_id=deeper.id),
            ]
        )
        session.commit()
        target_product_id = target_product.id
        target_product_name = target_product.nombre
        proposed = CategoriaAtributo(
            categoria_id=target.id,
            atributo_id=attribute.id,
            obligatorio=True,
            valor_default=None,
            activo=False,
        )

        _, affected, missing, names = service.required_attribute_impact(
            session, proposed, proposed=True
        )

    assert affected == [target_product_id]
    assert missing == [target_product_id]
    assert names[target_product_id] == target_product_name
    engine.dispose()


def test_backfill_only_targets_products_where_mapping_is_effective():
    engine = _build_test_engine()
    service = CategoriaAtributoService()

    with Session(engine) as session:
        parent = Categoria(nombre="Backfill parent", activo=True)
        session.add(parent)
        session.flush()
        child = Categoria(
            nombre="Backfill child", parent_id=parent.id, activo=True
        )
        attribute = Atributo(
            nombre=f"Backfill-{uuid4().hex[:8]}",
            tipo_dato=TipoDato.STRING,
            activo=True,
            usuario_auditoria="test",
        )
        parent_product = Producto(
            nombre=f"Parent-product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            activo=True,
            usuario_auditoria="test",
        )
        child_product = Producto(
            nombre=f"Child-product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            activo=True,
            usuario_auditoria="test",
        )
        inactive_product = Producto(
            nombre=f"Inactive-product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            activo=False,
            usuario_auditoria="test",
        )
        session.add_all([child, attribute, parent_product, child_product, inactive_product])
        session.flush()
        parent_mapping = CategoriaAtributo(
            categoria_id=parent.id,
            atributo_id=attribute.id,
            obligatorio=True,
            valor_default="Parent default",
            activo=True,
        )
        session.add_all(
            [
                parent_mapping,
                CategoriaAtributo(
                    categoria_id=child.id,
                    atributo_id=attribute.id,
                    obligatorio=False,
                    valor_default="Child override",
                    activo=True,
                ),
                ProductoCategoria(producto_id=parent_product.id, categoria_id=parent.id),
                ProductoCategoria(producto_id=child_product.id, categoria_id=parent.id),
                ProductoCategoria(producto_id=child_product.id, categoria_id=child.id),
                ProductoCategoria(producto_id=inactive_product.id, categoria_id=parent.id),
            ]
        )
        session.commit()

        service._ejecutar_backfill_atributo(
            session, parent_mapping, attribute.tipo_dato
        )

        values = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.atributo_id == attribute.id
            )
        ).all()
        values_by_product = {row.producto_id: row.valor_string for row in values}
        assert values_by_product == {parent_product.id: "Parent default"}
    engine.dispose()


def test_backfill_reactivates_valid_inactive_eav_identity_without_overwriting_value():
    engine = _build_test_engine()
    with Session(engine) as session:
        category = Categoria(nombre="Refurbished", activo=True)
        attribute = Atributo(
            nombre="Condition", tipo_dato=TipoDato.STRING, activo=True
        )
        products = [
            Producto(
                nombre=f"Device-{index}-{uuid4().hex[:6]}",
                tipo=TipoProducto.BIEN,
                pvp=Decimal("15.00"),
                activo=True,
            )
            for index in range(2)
        ]
        session.add_all([category, attribute, *products])
        session.flush()
        session.add_all(
            ProductoCategoria(producto_id=product.id, categoria_id=category.id)
            for product in products
        )
        inactive_value = ProductoAtributoValor(
            producto_id=products[0].id,
            atributo_id=attribute.id,
            valor_string="Reacondicionado",
            activo=False,
        )
        session.add(inactive_value)
        session.commit()
        inactive_value_id = inactive_value.id

        CategoriaAtributoService().create(
            session,
            CategoriaAtributoCreate(
                categoria_id=category.id,
                atributo_id=attribute.id,
                obligatorio=True,
                valor_default="Nuevo",
                aplicar_default_a_existentes=True,
            ),
        )

        rows = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.atributo_id == attribute.id
            )
        ).all()
        rows_by_product = {row.producto_id: row for row in rows}
        recovered = rows_by_product[products[0].id]
        assert recovered.id == inactive_value_id
        assert recovered.activo is True
        assert recovered.valor_string == "Reacondicionado"
        assert rows_by_product[products[1].id].valor_string == "Nuevo"
        audit = session.exec(
            select(AuditLog).where(AuditLog.registro_id == str(inactive_value_id))
        ).all()
        assert any(item.accion == "REACTIVATE_EAV_FOR_DEFAULT_BACKFILL" for item in audit)
    engine.dispose()


def test_local_removal_preserves_values_still_applicable_and_deactivates_displaced_values():
    engine = _build_test_engine()
    service = CategoriaAtributoService()
    with Session(engine) as session:
        root = Categoria(nombre="Computadores", activo=True)
        child = Categoria(nombre="Laptops", parent_id=root.id, activo=True)
        inherited_attribute = Atributo(
            nombre="Memoria RAM", tipo_dato=TipoDato.INTEGER, activo=True
        )
        local_attribute = Atributo(
            nombre="Teclado", tipo_dato=TipoDato.STRING, activo=True
        )
        product = Producto(
            nombre=f"Laptop-{uuid4().hex[:6]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            activo=True,
        )
        session.add_all([root, child, inherited_attribute, local_attribute, product])
        session.flush()
        ancestor_mapping = CategoriaAtributo(
            categoria_id=root.id,
            atributo_id=inherited_attribute.id,
            obligatorio=False,
            activo=True,
        )
        local_override = CategoriaAtributo(
            categoria_id=child.id,
            atributo_id=inherited_attribute.id,
            obligatorio=False,
            activo=True,
        )
        own_mapping = CategoriaAtributo(
            categoria_id=child.id,
            atributo_id=local_attribute.id,
            obligatorio=False,
            activo=True,
        )
        inherited_value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=inherited_attribute.id,
            valor_integer=16,
            activo=True,
        )
        local_value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=local_attribute.id,
            valor_string="ANSI",
            activo=True,
        )
        session.add_all(
            [
                ancestor_mapping,
                local_override,
                own_mapping,
                ProductoCategoria(producto_id=product.id, categoria_id=child.id),
                inherited_value,
                local_value,
            ]
        )
        session.commit()
        inherited_value_id = inherited_value.id
        local_value_id = local_value.id

        state, affected, remove_values, missing, _, retained_values, pending_remaps = (
            service.local_removal_impact(session, local_override)
        )
        assert affected == [product.id]
        assert remove_values == []
        assert missing == []
        assert retained_values == [inherited_value_id]
        assert pending_remaps == []

        service.remove_local_assignment(
            session, local_override, usuario_auditoria="actor-test"
        )
        session.refresh(inherited_value)
        session.refresh(local_override)
        assert local_override.activo is False
        assert inherited_value.activo is True

        _, _, remove_values, missing, _, retained_values, pending_remaps = (
            service.local_removal_impact(session, own_mapping)
        )
        assert remove_values == [local_value_id]
        assert retained_values == []
        assert missing == []
        assert pending_remaps == []
        service.remove_local_assignment(
            session, own_mapping, usuario_auditoria="actor-test"
        )
        session.refresh(local_value)
        assert own_mapping.activo is False
        assert local_value.activo is False
    engine.dispose()


def test_backfill_rejects_products_with_ambiguous_active_categories():
    engine = _build_test_engine()
    service = CategoriaAtributoService()

    with Session(engine) as session:
        parent = Categoria(nombre="Ambiguous parent", activo=True)
        session.add(parent)
        session.flush()
        child = Categoria(
            nombre="Ambiguous child", parent_id=parent.id, activo=True
        )
        sibling = Categoria(nombre="Ambiguous sibling", activo=True)
        attribute = Atributo(
            nombre=f"Ambiguous-{uuid4().hex[:8]}",
            tipo_dato=TipoDato.STRING,
            activo=True,
            usuario_auditoria="test",
        )
        product = Producto(
            nombre=f"Ambiguous-product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            activo=True,
            usuario_auditoria="test",
        )
        session.add_all([child, sibling, attribute, product])
        session.flush()
        parent_mapping = CategoriaAtributo(
            categoria_id=parent.id,
            atributo_id=attribute.id,
            obligatorio=True,
            valor_default="Parent default",
            activo=True,
        )
        session.add_all(
            [
                parent_mapping,
                CategoriaAtributo(
                    categoria_id=child.id,
                    atributo_id=attribute.id,
                    obligatorio=False,
                    valor_default=None,
                    activo=True,
                ),
                ProductoCategoria(producto_id=product.id, categoria_id=parent.id),
                ProductoCategoria(producto_id=product.id, categoria_id=sibling.id),
            ]
        )
        session.commit()

        with pytest.raises(HTTPException) as error:
            service._ejecutar_backfill_atributo(
                session, parent_mapping, attribute.tipo_dato
            )

        assert error.value.status_code == 409
        assert error.value.detail["code"] == "CATEGORY_ATTRIBUTE_SCOPE_AMBIGUOUS"
        assert error.value.detail["affected_ids"] == [str(product.id)]
        assert session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.atributo_id == attribute.id
            )
        ).all() == []
    engine.dispose()


@pytest.mark.parametrize("apply_default, expected_rows", [(True, 2), (False, 1)])
def test_update_optional_assignment_can_backfill_only_missing_product_values(
    apply_default, expected_rows
):
    engine = _build_test_engine()
    service = CategoriaAtributoService()

    with Session(engine) as session:
        category = Categoria(
            nombre="Categoría default",
            es_padre=False,
            activo=True,
            usuario_auditoria="test",
        )
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            activo=True,
            usuario_auditoria="test",
        )
        products = [
            Producto(
                nombre=f"Producto-default-{index}-{uuid4().hex[:8]}",
                tipo=TipoProducto.BIEN,
                pvp=Decimal("10"),
                activo=True,
                usuario_auditoria="test",
            )
            for index in range(2)
        ]
        session.add_all([category, attribute, *products])
        session.flush()
        assignment = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            obligatorio=False,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(assignment)
        session.add_all(
            ProductoCategoria(producto_id=product.id, categoria_id=category.id)
            for product in products
        )
        session.add(
            ProductoAtributoValor(
                producto_id=products[0].id,
                atributo_id=attribute.id,
                valor_string="Valor existente",
                activo=True,
                usuario_auditoria="test",
            )
        )
        session.commit()

        update = CategoriaAtributoUpdate(
            obligatorio=True,
            valor_default="Valor por defecto",
            aplicar_default_a_existentes=apply_default,
        )
        if apply_default:
            service.update(
                session, assignment.id, update, usuario_auditoria="test"
            )
        else:
            with pytest.raises(HTTPException) as error:
                service.update(
                    session, assignment.id, update, usuario_auditoria="test"
                )
            assert error.value.detail["code"] == "PRODUCT_REQUIRED_ATTRIBUTES_MISSING"
            session.refresh(assignment)
            assert assignment.obligatorio is False

        values = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.atributo_id == attribute.id
            )
        ).all()
        assert len(values) == expected_rows
        values_by_product = {row.producto_id: row.valor_string for row in values}
        assert values_by_product[products[0].id] == "Valor existente"
        if apply_default:
            assert values_by_product[products[1].id] == "Valor por defecto"
        else:
            assert products[1].id not in values_by_product


def test_atributos_duplicados_se_rechazan_globalmente_entre_categorias():
    engine = _build_test_engine()
    service = CategoriaAtributoService()

    with Session(engine) as session:
        root_a = Categoria(
            nombre="Rama A", es_padre=True, activo=True, usuario_auditoria="test"
        )
        child_a = Categoria(
            nombre="Hija A", es_padre=False, activo=True, usuario_auditoria="test"
        )
        root_b = Categoria(
            nombre="Rama B", es_padre=True, activo=True, usuario_auditoria="test"
        )
        session.add_all([root_a, child_a, root_b])
        session.flush()
        child_a.parent_id = root_a.id
        attribute_root = Atributo(
            nombre="Color",
            tipo_dato=TipoDato.STRING,
            activo=True,
            usuario_auditoria="test",
        )
        session.add(attribute_root)
        session.commit()

        service.create(
            session,
            CategoriaAtributoCreate(
                categoria_id=root_a.id, atributo_id=attribute_root.id
            ),
            usuario_auditoria="test",
        )

        override = service.create(
            session,
            CategoriaAtributoCreate(
                categoria_id=child_a.id, atributo_id=attribute_root.id
            ),
            usuario_auditoria="test",
        )
        assert override.atributo_id == attribute_root.id

        session.connection().exec_driver_sql(
            "DROP INDEX uq_tbl_atributo_nombre_activo_normalized"
        )
        attribute_conflict = Atributo(
            nombre=" color ",
            codigo="color_legacy_conflict",
            tipo_dato=TipoDato.STRING,
            activo=True,
            usuario_auditoria="test",
        )
        attribute_other_branch = Atributo(
            nombre="Color",
            codigo="color_legacy_other_branch",
            tipo_dato=TipoDato.STRING,
            activo=True,
            usuario_auditoria="test",
        )
        session.add_all([attribute_conflict, attribute_other_branch])
        session.commit()

        with pytest.raises(HTTPException, match="otra categoría") as exc_info:
            service.create(
                session,
                CategoriaAtributoCreate(
                    categoria_id=child_a.id, atributo_id=attribute_conflict.id
                ),
                usuario_auditoria="test",
            )
        assert exc_info.value.status_code == 409

        with pytest.raises(HTTPException, match="otra categoría") as exc_info:
            service.create(
                session,
                CategoriaAtributoCreate(
                    categoria_id=root_b.id, atributo_id=attribute_other_branch.id
                ),
                usuario_auditoria="test",
            )
        assert exc_info.value.status_code == 409
