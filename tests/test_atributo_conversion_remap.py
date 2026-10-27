from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo, CatalogoValor
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.inventario.atributo.entity import Atributo, AtributoCambio, TipoDato
from osiris.modules.inventario.atributo.remap_service import AtributoRemapeoService
from osiris.modules.inventario.atributo.service import AtributoService
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoCategoria,
    TipoProducto,
)
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeo,
    ProductoAtributoValor,
)
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeoResolve,
)


def _engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AuditLog.__table__,
            Catalogo.__table__,
            CatalogoValor.__table__,
            CasaComercial.__table__,
            Unidad.__table__,
            Atributo.__table__,
            AtributoCambio.__table__,
            Categoria.__table__,
            CategoriaAtributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoAtributoValor.__table__,
            ProductoAtributoRemapeo.__table__,
        ],
    )
    return engine


def test_type_change_converts_valid_values_and_preserves_invalid_values_for_remap():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        valid_product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        invalid_product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, valid_product, invalid_product])
        session.flush()
        category = Categoria(
            nombre=f"Categoria-{uuid4().hex[:8]}",
            es_padre=False,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(category)
        session.flush()
        session.add_all(
            [
                ProductoCategoria(
                    producto_id=valid_product.id, categoria_id=category.id
                ),
                ProductoCategoria(
                    producto_id=invalid_product.id, categoria_id=category.id
                ),
                CategoriaAtributo(
                    categoria_id=category.id,
                    atributo_id=attribute.id,
                    obligatorio=False,
                    usuario_auditoria="test",
                    activo=True,
                ),
            ]
        )
        valid_value = ProductoAtributoValor(
            producto_id=valid_product.id,
            atributo_id=attribute.id,
            valor_string="42",
            usuario_auditoria="test",
            activo=True,
        )
        invalid_value = ProductoAtributoValor(
            producto_id=invalid_product.id,
            atributo_id=attribute.id,
            valor_string="n/a",
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([valid_value, invalid_value])
        session.commit()

        updated = AtributoService().update(
            session, attribute.id, {"tipo_dato": TipoDato.INTEGER}
        )

        assert updated.tipo_dato == TipoDato.INTEGER
        session.refresh(valid_value)
        session.refresh(invalid_value)
        assert valid_value.valor_integer == 42
        assert valid_value.valor_string is None
        assert invalid_value.valor_string == "n/a"
        remaps = session.exec(
            select(ProductoAtributoRemapeo).where(
                ProductoAtributoRemapeo.atributo_id == attribute.id
            )
        ).all()
        assert len(remaps) == 1
        assert remaps[0].producto_id == invalid_product.id
        assert remaps[0].valor_anterior == {"value": "n/a"}
        assert remaps[0].activo is True

        remap_service = AtributoRemapeoService()
        pending = remap_service.listar_pendientes(session)
        assert pending["total"] == 1
        assert pending["groups"][0]["target_type"] == "integer"
        result = remap_service.resolver(
            session,
            [ProductoAtributoRemapeoResolve(id=remaps[0].id, valor=7)],
        )
        assert result == {"resolved": 1}
        session.refresh(invalid_value)
        session.refresh(remaps[0])
        assert invalid_value.valor_integer == 7
        assert invalid_value.valor_string is None
        assert remaps[0].activo is False
        with pytest.raises(HTTPException) as undo_error:
            AtributoService().undo(session, attribute.id)
        assert undo_error.value.status_code == 409


def test_required_attribute_conversion_blocks_incompatible_values_before_remap():
    engine = _engine()
    with Session(engine) as session:
        category = Categoria(nombre=f"Required-{uuid4().hex[:8]}", activo=True)
        attribute = Atributo(
            nombre=f"Required value-{uuid4().hex[:8]}",
            tipo_dato=TipoDato.STRING,
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            activo=True,
        )
        session.add_all([category, attribute, product])
        session.flush()
        mapping = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            obligatorio=True,
            activo=True,
        )
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_string="n/a",
            activo=True,
        )
        session.add_all(
            [
                mapping,
                value,
                ProductoCategoria(producto_id=product.id, categoria_id=category.id),
            ]
        )
        session.commit()

        with pytest.raises(HTTPException) as preview_error:
            AtributoService().preview_update(
                session, attribute.id, {"tipo_dato": TipoDato.INTEGER}
            )
        assert preview_error.value.status_code == 409
        assert preview_error.value.detail["code"] == "PRODUCT_REQUIRED_ATTRIBUTES_MISSING"
        assert session.exec(select(ProductoAtributoRemapeo)).all() == []

        with pytest.raises(HTTPException) as error:
            AtributoService().update(
                session, attribute.id, {"tipo_dato": TipoDato.INTEGER}
            )

        assert error.value.status_code == 409
        assert error.value.detail["code"] == "PRODUCT_REQUIRED_ATTRIBUTES_MISSING"
        assert session.get(Atributo, attribute.id).tipo_dato == TipoDato.STRING
        assert session.exec(select(ProductoAtributoRemapeo)).all() == []
        current_value = session.get(ProductoAtributoValor, value.id)
        assert current_value is not None
        assert current_value.valor_string == "n/a"
    engine.dispose()


def test_preview_is_read_only_and_undo_restores_attribute_and_value():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, product])
        session.flush()
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_string="42",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(value)
        session.commit()

        preview = AtributoService().preview_update(
            session, attribute.id, {"tipo_dato": TipoDato.INTEGER}
        )
        assert preview["convertibles"] == 1
        assert preview["incompatibles"] == []
        assert session.exec(select(AtributoCambio)).all() == []
        session.refresh(value)
        assert value.valor_string == "42"
        assert value.valor_integer is None

        AtributoService().update(session, attribute.id, {"tipo_dato": TipoDato.INTEGER})
        result = AtributoService().undo(session, attribute.id)

        assert result["operacion"] == "update"
        session.refresh(attribute)
        session.refresh(value)
        assert attribute.tipo_dato == TipoDato.STRING
        assert value.valor_string == "42"
        assert value.valor_integer is None


def test_preview_update_reports_effective_categories_with_local_override_scope():
    engine = _engine()
    with Session(engine) as session:
        parent = Categoria(nombre="Preview parent", activo=True)
        session.add(parent)
        session.flush()
        child = Categoria(nombre="Preview child", parent_id=parent.id, activo=True)
        attribute = Atributo(
            nombre="Preview attribute",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([child, attribute])
        session.flush()
        parent_mapping = CategoriaAtributo(
            categoria_id=parent.id,
            atributo_id=attribute.id,
            obligatorio=False,
            valor_default="ancestor",
            activo=True,
        )
        child_mapping = CategoriaAtributo(
            categoria_id=child.id,
            atributo_id=attribute.id,
            obligatorio=False,
            valor_default=None,
            activo=True,
        )
        session.add_all([parent_mapping, child_mapping])
        session.commit()

        preview = AtributoService().preview_update(
            session, attribute.id, {"nombre": "Preview attribute renamed"}
        )

        scopes = {
            item["categoria_id"]: item for item in preview["categorias_efectivas"]
        }
        assert scopes[str(parent.id)]["mapping_id"] == str(parent_mapping.id)
        assert scopes[str(child.id)]["mapping_id"] == str(child_mapping.id)
        assert scopes[str(child.id)]["categoria_origen"] == {
            "id": str(child.id),
            "nombre": child.nombre,
        }


def test_undo_rejects_attribute_values_changed_after_snapshot():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, product])
        session.flush()
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_string="42",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(value)
        session.commit()

        AtributoService().update(session, attribute.id, {"tipo_dato": TipoDato.INTEGER})
        value.valor_integer = 43
        session.add(value)
        session.commit()

        with pytest.raises(HTTPException) as error:
            AtributoService().undo(session, attribute.id)

        assert error.value.status_code == 409


def test_deactivate_and_reactivate_restores_assignments_and_values():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        category = Categoria(
            nombre=f"Categoria-{uuid4().hex[:8]}",
            es_padre=False,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, category, product])
        session.flush()
        assignment = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            usuario_auditoria="test",
            activo=True,
        )
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_string="12 meses",
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([assignment, value])
        session.commit()

        AtributoService().delete(session, attribute.id)
        assert (
            AtributoService().lifecycle_status(session, attribute.id)["can_reactivate"]
            is True
        )
        result = AtributoService().reactivate(session, attribute.id)

        assert result["operacion"] == "deactivate"
        session.refresh(attribute)
        session.refresh(assignment)
        session.refresh(value)
        assert attribute.activo is True
        assert assignment.activo is True
        assert value.activo is True


def test_undo_reverts_latest_definition_change_first():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(attribute)
        session.commit()
        attribute_id = attribute.id

        AtributoService().update(
            session, attribute_id, {"nombre": "Garantía extendida"}
        )
        AtributoService().update(
            session, attribute_id, {"nombre": "Garantía comercial"}
        )
        AtributoService().undo(session, attribute_id)
        session.refresh(attribute)
        assert attribute.nombre == "Garantía extendida"
        AtributoService().undo(session, attribute_id)
        session.refresh(attribute)
        assert attribute.nombre == "Garantía"
        assert attribute.id == attribute_id


def test_undo_conversion_restores_values_and_removes_its_pending_remap():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, product])
        session.flush()
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_string="n/a",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(value)
        session.commit()

        AtributoService().update(session, attribute.id, {"nombre": "Garantía revisada"})
        AtributoService().update(session, attribute.id, {"tipo_dato": TipoDato.INTEGER})
        remap = session.exec(select(ProductoAtributoRemapeo)).first()
        assert remap is not None and remap.activo is True
        AtributoService().undo(session, attribute.id)

        session.refresh(attribute)
        session.refresh(value)
        session.refresh(remap)
        assert attribute.tipo_dato == TipoDato.STRING
        assert attribute.nombre == "Garantía revisada"
        assert value.valor_string == "n/a"
        assert remap.activo is False
        AtributoService().undo(session, attribute.id)
        session.refresh(attribute)
        assert attribute.nombre == "Garantía"


def test_legacy_inactive_attribute_cannot_be_reactivated_without_snapshot():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía legacy",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=False,
        )
        session.add(attribute)
        session.commit()

        status = AtributoService().lifecycle_status(session, attribute.id)
        assert status["can_reactivate"] is False
        assert "recuperación administrativa" in status["motivo"]
        with pytest.raises(HTTPException) as error:
            AtributoService().reactivate(session, attribute.id)

        assert error.value.status_code == 409
        session.refresh(attribute)
        assert attribute.activo is False


def test_deactivate_rejects_pending_remaps_without_mutating_attribute():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.INTEGER,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, product])
        session.flush()
        remap = ProductoAtributoRemapeo(
            producto_id=product.id,
            atributo_id=attribute.id,
            tipo_anterior="string",
            tipo_nuevo="integer",
            valor_anterior={"value": "n/a"},
            motivo="invalid integer",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(remap)
        session.commit()

        with pytest.raises(HTTPException) as error:
            AtributoService().delete(session, attribute.id)

        assert error.value.status_code == 409
        session.refresh(attribute)
        session.refresh(remap)
        assert attribute.activo is True
        assert remap.activo is True


def test_update_rolls_back_values_remaps_and_snapshot_when_audit_fails(monkeypatch):
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, product])
        session.flush()
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_string="n/a",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(value)
        session.commit()

        def fail_update_audit(*_args, **kwargs):
            if kwargs.get("action") == "UPDATE_ATTRIBUTE":
                raise RuntimeError("audit failure")

        monkeypatch.setattr(
            "osiris.modules.inventario.atributo.service.record_domain_change",
            fail_update_audit,
        )
        with pytest.raises(RuntimeError, match="audit failure"):
            AtributoService().update(
                session, attribute.id, {"tipo_dato": TipoDato.INTEGER}
            )

        session.refresh(attribute)
        session.refresh(value)
        assert attribute.tipo_dato == TipoDato.STRING
        assert value.valor_string == "n/a"
        assert session.exec(select(ProductoAtributoRemapeo)).all() == []
        assert session.exec(select(AtributoCambio)).all() == []


def test_preview_numeric_bounds_and_inactive_catalog_are_validation_only():
    engine = _engine()
    with Session(engine) as session:
        numeric = Atributo(
            nombre="Peso",
            tipo_dato=TipoDato.INTEGER,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        inactive_catalog = Catalogo(
            nombre="Garantías", usuario_auditoria="test", activo=False
        )
        session.add_all([numeric, product, inactive_catalog])
        session.flush()
        session.add(
            ProductoAtributoValor(
                producto_id=product.id,
                atributo_id=numeric.id,
                valor_integer=3,
                usuario_auditoria="test",
                activo=True,
            )
        )
        catalog_attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(catalog_attribute)
        session.commit()

        preview = AtributoService().preview_update(
            session, numeric.id, {"min_value": Decimal("5")}
        )
        assert preview["incompatibles"][0]["motivo"] == "below configured minimum"
        with pytest.raises(HTTPException) as error:
            AtributoService().preview_update(
                session,
                catalog_attribute.id,
                {"tipo_dato": TipoDato.CATALOG, "catalog_id": inactive_catalog.id},
            )

        assert error.value.status_code == 400
        assert session.exec(select(AtributoCambio)).all() == []
        assert session.exec(select(ProductoAtributoRemapeo)).all() == []
        session.refresh(inactive_catalog)
        assert inactive_catalog.activo is False


def test_undo_rejects_new_category_assignment_after_snapshot():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        category = Categoria(
            nombre=f"Categoria-{uuid4().hex[:8]}",
            es_padre=False,
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, category])
        session.commit()

        AtributoService().update(
            session, attribute.id, {"nombre": "Garantía extendida"}
        )
        assignment = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(assignment)
        session.commit()

        with pytest.raises(HTTPException) as error:
            AtributoService().undo(session, attribute.id)

        assert error.value.status_code == 409
        session.refresh(attribute)
        session.refresh(assignment)
        assert attribute.nombre == "Garantía extendida"
        assert assignment.activo is True


def test_deactivation_rolls_back_attribute_assignments_values_and_snapshot(monkeypatch):
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        category = Categoria(
            nombre=f"Categoria-{uuid4().hex[:8]}",
            es_padre=False,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, category, product])
        session.flush()
        assignment = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            usuario_auditoria="test",
            activo=True,
        )
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_string="12 meses",
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([assignment, value])
        session.commit()

        def fail_delete_audit(*_args, **kwargs):
            if kwargs.get("action") == "DELETE_ATTRIBUTE":
                raise RuntimeError("audit failure")

        monkeypatch.setattr(
            "osiris.modules.inventario.atributo.service.record_domain_change",
            fail_delete_audit,
        )
        with pytest.raises(RuntimeError, match="audit failure"):
            AtributoService().delete(session, attribute.id)

        session.refresh(attribute)
        session.refresh(assignment)
        session.refresh(value)
        assert attribute.activo is True
        assert assignment.activo is True
        assert value.activo is True
        assert session.exec(select(AtributoCambio)).all() == []


def test_preview_same_type_constraints_reports_invalid_values_without_writes():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Talla",
            tipo_dato=TipoDato.SELECT,
            select_options=["S", "M"],
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, product])
        session.flush()
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_string="S",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(value)
        session.commit()

        preview = AtributoService().preview_update(
            session, attribute.id, {"select_options": ["M", "L"]}
        )

        assert preview["incompatibles"] == [
            {
                "producto_id": str(product.id),
                "valor": "S",
                "motivo": "value is not in select options",
            }
        ]
        assert preview["productos_afectados"] == 1
        assert preview["requiere_confirmacion"] is True
        assert session.exec(select(AtributoCambio)).all() == []
        assert session.exec(select(ProductoAtributoRemapeo)).all() == []
        session.refresh(value)
        assert value.valor_string == "S"


def test_preview_catalog_without_existing_catalog_does_not_create_one():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, product])
        session.flush()
        session.add(
            ProductoAtributoValor(
                producto_id=product.id,
                atributo_id=attribute.id,
                valor_string="12 meses",
                usuario_auditoria="test",
                activo=True,
            )
        )
        session.commit()

        preview = AtributoService().preview_update(
            session, attribute.id, {"tipo_dato": TipoDato.CATALOG}
        )

        assert preview["incompatibles"][0]["motivo"] == "catalog is missing"
        assert session.exec(select(Catalogo)).all() == []
        assert session.exec(select(AtributoCambio)).all() == []
