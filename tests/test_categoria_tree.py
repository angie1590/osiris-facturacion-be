from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, select

from osiris.core.db import get_session
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.models import CategoriaCreate, CategoriaRead
from osiris.modules.inventario.categoria.router import (
    assign_category_attribute_permission,
    create_category_permission,
    reactivate_category_permission,
    read_category_attributes_permission,
    read_categories_permission,
    router,
    update_category_permission,
)
from osiris.modules.inventario.categoria.tree import get_category_tree
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.categoria_atributo.models import CategoriaAtributoUpdate
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria, TipoProducto
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeo,
    ProductoAtributoValor,
)
from osiris.modules.common.unidad.entity import Unidad
from tests.test_categoria_regla_b3 import _build_test_engine


def _client(
    session: Session, actor: SimpleNamespace | None = None
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[read_categories_permission] = lambda: None
    app.dependency_overrides[read_category_attributes_permission] = lambda: None
    assignment_actor = actor or SimpleNamespace(id=uuid4())
    app.dependency_overrides[assign_category_attribute_permission] = lambda: assignment_actor
    app.dependency_overrides[reactivate_category_permission] = lambda: None
    actor = SimpleNamespace(id=uuid4())
    app.dependency_overrides[create_category_permission] = lambda: actor
    app.dependency_overrides[update_category_permission] = lambda: actor
    return TestClient(app)


def test_category_tree_is_ordered_derived_and_counts_effective_overrides() -> None:
    engine = _build_test_engine()
    with Session(engine) as session:
        root = Categoria(nombre="Alpha", es_padre=False, activo=True)
        other_root = Categoria(nombre="Zulu", es_padre=True, activo=True)
        session.add_all([root, other_root])
        session.flush()
        child = Categoria(nombre="Child", parent_id=root.id, activo=True)
        session.add(child)
        session.flush()
        leaf = Categoria(nombre="Leaf", parent_id=child.id, activo=True)
        bucket = Categoria(
            nombre="Sin clasificar",
            parent_id=root.id,
            is_default=True,
            activo=True,
        )
        inactive_child = Categoria(
            nombre="Inactive", parent_id=other_root.id, activo=False
        )
        attribute = Atributo(
            nombre="Color", codigo="color", tipo_dato=TipoDato.STRING, activo=True
        )
        inactive_attribute = Atributo(
            nombre="Legacy", codigo="legacy", tipo_dato=TipoDato.STRING, activo=False
        )
        session.add_all([leaf, bucket, inactive_child, attribute, inactive_attribute])
        session.flush()
        root_mapping = CategoriaAtributo(
            categoria_id=root.id,
            atributo_id=attribute.id,
            orden=1,
            obligatorio=False,
            valor_default="red",
        )
        child_mapping = CategoriaAtributo(
            categoria_id=child.id,
            atributo_id=attribute.id,
            orden=2,
            obligatorio=False,
            valor_default=None,
        )
        session.add_all(
            [
                root_mapping,
                child_mapping,
                CategoriaAtributo(categoria_id=leaf.id, atributo_id=inactive_attribute.id),
            ]
        )
        session.commit()

        client = _client(session)
        response = client.get("/api/v1/categorias/arbol")
        assert response.status_code == 200
        roots = response.json()
        assert [item["nombre"] for item in roots] == ["Alpha", "Zulu"]
        alpha = roots[0]
        assert alpha["tiene_hijos"] is True
        assert alpha["atributos_propios_count"] == 1
        assert alpha["atributos_efectivos_count"] == 1
        assert [item["nombre"] for item in alpha["hijos"]] == [
            "Child",
            "Sin clasificar",
        ]
        child_node = alpha["hijos"][0]
        leaf_node = child_node["hijos"][0]
        assert child_node["atributos_propios_count"] == 1
        assert child_node["atributos_efectivos_count"] == 1
        assert leaf_node["tiene_hijos"] is False
        assert leaf_node["atributos_propios_count"] == 0
        assert leaf_node["atributos_efectivos_count"] == 1
        from osiris.modules.inventario.categoria.service import CategoriaService

        resolved = CategoriaService().get_atributos_heredados_por_categoria(
            session, leaf.id
        )
        assert len(resolved) == leaf_node["atributos_efectivos_count"]
        assert resolved[0]["atributo_id"] == attribute.id
        assert resolved[0]["mapping_id"] == child_mapping.id
        assert resolved[0]["categoria_origen_id"] == child.id
        assert resolved[0]["profundidad"] == 1
        assert resolved[0]["valor_default"] is None
        assert resolved[0]["orden"] == 2
        assert roots[1]["tiene_hijos"] is False

        selectable_response = client.get("/api/v1/categorias/seleccionables")
        assert selectable_response.status_code == 200
        assert [item["nombre"] for item in selectable_response.json()] == [
            "Leaf",
            "Zulu",
        ]
        assert all(item["tiene_hijos"] is False for item in selectable_response.json())
        assert all(item["is_default"] is False for item in selectable_response.json())
    engine.dispose()


def test_inherited_attribute_configuration_creates_local_override() -> None:
    engine = _build_test_engine()
    with Session(engine) as session:
        parent = Categoria(nombre="Computadores", es_padre=True, activo=True)
        session.add(parent)
        session.flush()
        child = Categoria(nombre="Laptops", parent_id=parent.id, activo=True)
        attribute = Atributo(
            nombre="Memoria RAM", codigo="memoria_ram", tipo_dato=TipoDato.INTEGER, activo=True
        )
        session.add_all([child, attribute])
        session.flush()
        parent_mapping = CategoriaAtributo(
            categoria_id=parent.id,
            atributo_id=attribute.id,
            obligatorio=False,
            valor_default="8",
            orden=2,
            activo=True,
        )
        session.add(parent_mapping)
        session.commit()
        parent_mapping_id = parent_mapping.id
        parent_category_id = parent.id
        child_category_id = child.id
        attribute_id = attribute.id

        client = _client(session)
        payload = {
            "atributo_id": str(attribute_id),
            "obligatorio": True,
            "valor_default": 16,
            "orden": 1,
            "aplicar_default_a_existentes": False,
        }
        preview = client.post(
            f"/api/v1/categorias/{child_category_id}/atributos/previsualizar",
            json=payload,
        )
        assert preview.status_code == 200, preview.text
        response = client.post(
            f"/api/v1/categorias/{child_category_id}/atributos",
            json={**payload, "precondicion_preview": preview.json()["precondicion_preview"]},
        )

        assert response.status_code == 201, response.text
        child_mapping = session.exec(
            select(CategoriaAtributo).where(
                CategoriaAtributo.categoria_id == child_category_id,
                CategoriaAtributo.atributo_id == attribute_id,
            )
        ).one()
        parent_after = session.get(CategoriaAtributo, parent_mapping_id)

        assert response.json()["categoria_origen"]["id"] == str(child_category_id)
        assert child_mapping.atributo_id == attribute_id
        assert child_mapping.id != parent_mapping_id
        assert parent_after is not None
        assert parent_after.categoria_id == parent_category_id
        assert parent_after.obligatorio is False
        assert parent_after.valor_default == "8"
        assert parent_after.orden == 2


def test_relationship_update_dto_rejects_global_definition_fields() -> None:
    with pytest.raises(ValueError):
        CategoriaAtributoUpdate.model_validate(
            {"obligatorio": True, "nombre": "Nombre global"}
        )


def test_contextual_mapping_update_is_scoped_and_uses_jwt_actor() -> None:
    engine = _build_test_engine()
    actor = SimpleNamespace(id=uuid4())
    with Session(engine) as session:
        category = Categoria(nombre="Periféricos", es_padre=False, activo=True)
        other_category = Categoria(nombre="Audio", es_padre=False, activo=True)
        attribute = Atributo(
            nombre="Conectividad", codigo="conectividad", tipo_dato=TipoDato.STRING, activo=True
        )
        session.add_all([category, other_category, attribute])
        session.flush()
        mapping = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            obligatorio=False,
            valor_default=None,
            activo=True,
        )
        session.add(mapping)
        session.commit()

        client = _client(session, actor)
        wrong_scope = client.put(
            f"/api/v1/categorias/{other_category.id}/atributos/{mapping.id}",
            json={"orden": 3},
        )
        assert wrong_scope.status_code == 404
        response = client.put(
            f"/api/v1/categorias/{category.id}/atributos/{mapping.id}",
            json={"orden": 3},
        )

        assert response.status_code == 200, response.text
        assert response.json()["mapping_id"] == str(mapping.id)
        assert response.json()["orden"] == 3
        assert mapping.usuario_auditoria == str(actor.id)
    engine.dispose()


def test_required_attribute_preview_reports_missing_and_rejects_stale_confirmation() -> None:
    engine = _build_test_engine()
    SQLModel.metadata.create_all(engine, tables=[ProductoAtributoValor.__table__])
    actor = SimpleNamespace(id=uuid4())
    with Session(engine) as session:
        category = Categoria(nombre="Cámaras", es_padre=False, activo=True)
        attribute = Atributo(
            nombre="Sensor", codigo="sensor", tipo_dato=TipoDato.STRING, activo=True
        )
        product = Producto(
            nombre="Cámara sin sensor",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            categoria_principal_id=category.id,
            activo=True,
        )
        session.add_all([category, attribute, product])
        session.flush()
        mapping = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            obligatorio=False,
            activo=True,
        )
        session.add_all(
            [mapping, ProductoCategoria(producto_id=product.id, categoria_id=category.id)]
        )
        session.commit()

        client = _client(session, actor)
        request_payload = {
            "obligatorio": True,
            "valor_default": None,
            "aplicar_default_a_existentes": False,
        }
        preview = client.post(
            f"/api/v1/categorias/{category.id}/atributos/{mapping.id}/previsualizar",
            json=request_payload,
        )
        assert preview.status_code == 200, preview.text
        preview_data = preview.json()
        assert preview_data["conteos"]["productos_afectados"] == 1
        assert preview_data["conteos"]["productos_faltantes"] == 1
        assert preview_data["faltantes"] == [
            {
                "id": str(product.id),
                "nombre": product.nombre,
                "motivo": "No tiene un valor EAV activo válido para este atributo.",
            }
        ]
        incomplete = client.put(
            f"/api/v1/categorias/{category.id}/atributos/{mapping.id}",
            json={
                **request_payload,
                "precondicion_preview": preview_data["precondicion_preview"],
            },
        )
        assert incomplete.status_code == 409
        assert incomplete.json()["detail"]["code"] == "PRODUCT_REQUIRED_ATTRIBUTES_MISSING"
        session.refresh(mapping)
        assert mapping.obligatorio is False

        session.add(
            ProductoAtributoValor(
                producto_id=product.id,
                atributo_id=attribute.id,
                valor_string="CMOS",
                activo=True,
            )
        )
        session.commit()
        confirmation = client.put(
            f"/api/v1/categorias/{category.id}/atributos/{mapping.id}",
            json={**request_payload, "precondicion_preview": preview_data["precondicion_preview"]},
        )

        assert confirmation.status_code == 409
        assert confirmation.json()["detail"]["code"] == "CATALOG_PREVIEW_STALE"
        session.refresh(mapping)
        assert mapping.obligatorio is False

        fresh_preview = client.post(
            f"/api/v1/categorias/{category.id}/atributos/{mapping.id}/previsualizar",
            json=request_payload,
        )
        assert fresh_preview.status_code == 200, fresh_preview.text
        assert fresh_preview.json()["conteos"]["productos_faltantes"] == 0
        applied = client.put(
            f"/api/v1/categorias/{category.id}/atributos/{mapping.id}",
            json={
                **request_payload,
                "precondicion_preview": fresh_preview.json()["precondicion_preview"],
            },
        )
        assert applied.status_code == 200, applied.text
        session.refresh(mapping)
        assert mapping.obligatorio is True
    engine.dispose()


def test_required_assignment_needs_opt_in_backfill_to_create_missing_values() -> None:
    engine = _build_test_engine()
    SQLModel.metadata.create_all(engine, tables=[ProductoAtributoValor.__table__])
    actor = SimpleNamespace(id=uuid4())
    with Session(engine) as session:
        category = Categoria(nombre="Monitores", activo=True)
        attribute = Atributo(
            nombre="Panel",
            codigo="panel",
            tipo_dato=TipoDato.STRING,
            activo=True,
        )
        product = Producto(
            nombre="Monitor sin panel",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            categoria_principal_id=category.id,
            activo=True,
        )
        session.add_all([category, attribute, product])
        session.flush()
        session.add(ProductoCategoria(producto_id=product.id, categoria_id=category.id))
        session.commit()
        client = _client(session, actor)

        incomplete_payload = {
            "atributo_id": str(attribute.id),
            "obligatorio": True,
            "valor_default": None,
            "aplicar_default_a_existentes": False,
        }
        preview = client.post(
            f"/api/v1/categorias/{category.id}/atributos/previsualizar",
            json=incomplete_payload,
        )
        assert preview.status_code == 200, preview.text
        blocked = client.post(
            f"/api/v1/categorias/{category.id}/atributos",
            json={
                **incomplete_payload,
                "precondicion_preview": preview.json()["precondicion_preview"],
            },
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"]["code"] == "PRODUCT_REQUIRED_ATTRIBUTES_MISSING"
        assert session.exec(select(CategoriaAtributo)).all() == []
        assert session.exec(select(ProductoAtributoValor)).all() == []

        backfill_payload = {
            **incomplete_payload,
            "valor_default": "IPS",
            "aplicar_default_a_existentes": True,
        }
        backfill_preview = client.post(
            f"/api/v1/categorias/{category.id}/atributos/previsualizar",
            json=backfill_payload,
        )
        assert backfill_preview.status_code == 200, backfill_preview.text
        applied = client.post(
            f"/api/v1/categorias/{category.id}/atributos",
            json={
                **backfill_payload,
                "precondicion_preview": backfill_preview.json()["precondicion_preview"],
            },
        )
        assert applied.status_code == 201, applied.text
        value = session.exec(select(ProductoAtributoValor)).one()
        assert value.valor_string == "IPS"
    engine.dispose()


def test_local_removal_preview_and_delete_preserve_ancestral_eav_value() -> None:
    engine = _build_test_engine()
    SQLModel.metadata.create_all(
        engine,
        tables=[ProductoAtributoValor.__table__, ProductoAtributoRemapeo.__table__],
    )
    actor = SimpleNamespace(id=uuid4())
    with Session(engine) as session:
        root = Categoria(nombre="Computadores", activo=True)
        session.add(root)
        session.flush()
        child = Categoria(nombre="Laptops", parent_id=root.id, activo=True)
        attribute = Atributo(
            nombre="Memoria RAM", codigo="memoria_ram", tipo_dato=TipoDato.INTEGER, activo=True
        )
        product = Producto(
            nombre="Laptop 16GB",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            categoria_principal_id=child.id,
            activo=True,
        )
        session.add_all([child, attribute, product])
        session.flush()
        ancestor = CategoriaAtributo(
            categoria_id=root.id,
            atributo_id=attribute.id,
            obligatorio=False,
            activo=True,
        )
        local = CategoriaAtributo(
            categoria_id=child.id,
            atributo_id=attribute.id,
            obligatorio=False,
            activo=True,
        )
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_integer=16,
            activo=True,
        )
        session.add_all(
            [
                ancestor,
                local,
                value,
                ProductoCategoria(producto_id=product.id, categoria_id=child.id),
            ]
        )
        session.commit()
        category_id = child.id
        mapping_id = local.id
        value_id = value.id
        client = _client(session, actor)

        preview = client.post(
            f"/api/v1/categorias/{category_id}/atributos/{mapping_id}/previsualizar-remocion"
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["conteos"]["valores_conservados"] == 1
        assert preview.json()["conteos"]["valores_desactivados"] == 0
        removed = client.request(
            "DELETE",
            f"/api/v1/categorias/{category_id}/atributos/{mapping_id}",
            json={
                "confirmar": True,
                "precondicion_preview": preview.json()["precondicion_preview"],
            },
        )
        assert removed.status_code == 200, removed.text
        session.refresh(local)
        value_after = session.get(ProductoAtributoValor, value_id)
        assert local.activo is False
        assert value_after is not None
        assert value_after.activo is True
        assert session.get(CategoriaAtributo, ancestor.id).activo is True
    engine.dispose()


def test_local_removal_with_pending_remap_is_blocked_without_mutation() -> None:
    engine = _build_test_engine()
    SQLModel.metadata.create_all(
        engine,
        tables=[ProductoAtributoValor.__table__, ProductoAtributoRemapeo.__table__],
    )
    actor = SimpleNamespace(id=uuid4())
    with Session(engine) as session:
        category = Categoria(nombre="Cámaras", activo=True)
        attribute = Atributo(
            nombre="Resolución",
            codigo="resolucion",
            tipo_dato=TipoDato.INTEGER,
            activo=True,
        )
        product = Producto(
            nombre="Cámara remapeo",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            categoria_principal_id=category.id,
            activo=True,
        )
        session.add_all([category, attribute, product])
        session.flush()
        mapping = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            obligatorio=False,
            activo=True,
        )
        remap = ProductoAtributoRemapeo(
            producto_id=product.id,
            atributo_id=attribute.id,
            tipo_anterior="string",
            tipo_nuevo="integer",
            valor_anterior={"value": "4k"},
            motivo="invalid integer",
            activo=True,
        )
        session.add_all(
            [mapping, remap, ProductoCategoria(producto_id=product.id, categoria_id=category.id)]
        )
        session.commit()
        client = _client(session, actor)
        preview = client.post(
            f"/api/v1/categorias/{category.id}/atributos/{mapping.id}/previsualizar-remocion"
        )
        assert preview.status_code == 200, preview.text
        assert len(preview.json()["remapeos"]) == 1
        response = client.request(
            "DELETE",
            f"/api/v1/categorias/{category.id}/atributos/{mapping.id}",
            json={
                "confirmar": True,
                "precondicion_preview": preview.json()["precondicion_preview"],
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "ATTRIBUTE_HAS_PENDING_REMAPS"
        session.refresh(mapping)
        assert mapping.activo is True
    engine.dispose()


def test_category_tree_rejects_cycles_without_recursing_forever() -> None:
    engine = _build_test_engine()
    with Session(engine) as session:
        first = Categoria(nombre="First", activo=True)
        second = Categoria(nombre="Second", activo=True)
        session.add_all([first, second])
        session.flush()
        first.parent_id = second.id
        second.parent_id = first.id
        session.add_all([first, second])
        session.commit()

        response = _client(session).get("/api/v1/categorias/arbol")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "CATEGORY_CYCLE"
    engine.dispose()


def test_effective_and_own_attribute_routes_return_canonical_override_unit_and_order() -> None:
    engine = _build_test_engine()
    with Session(engine) as session:
        parent = Categoria(nombre="Parent", activo=True)
        session.add(parent)
        session.flush()
        child = Categoria(nombre="Child", parent_id=parent.id, activo=True)
        unit = Unidad(
            codigo="GB",
            nombre="Gigabyte",
            simbolo="GB",
            magnitud_codigo="DATA_STORAGE",
            activo=True,
        )
        session.add_all([child, unit])
        session.flush()
        storage = Atributo(
            nombre="Zeta almacenamiento",
            codigo="almacenamiento",
            tipo_dato=TipoDato.INTEGER,
            unidad_id=unit.id,
            activo=True,
        )
        bandwidth = Atributo(
            nombre="Ancho de banda",
            codigo="ancho_de_banda",
            tipo_dato=TipoDato.INTEGER,
            activo=True,
        )
        inherited = Atributo(
            nombre="Marca",
            codigo="marca",
            tipo_dato=TipoDato.STRING,
            activo=True,
        )
        session.add_all([storage, bandwidth, inherited])
        session.flush()
        parent_storage = CategoriaAtributo(
            categoria_id=parent.id,
            atributo_id=storage.id,
            orden=5,
            obligatorio=False,
            valor_default="32",
            activo=True,
        )
        child_storage = CategoriaAtributo(
            categoria_id=child.id,
            atributo_id=storage.id,
            orden=1,
            obligatorio=True,
            valor_default=None,
            activo=True,
        )
        parent_inherited = CategoriaAtributo(
            categoria_id=parent.id,
            atributo_id=inherited.id,
            activo=True,
        )
        session.add_all(
            [
                parent_storage,
                child_storage,
                parent_inherited,
                CategoriaAtributo(
                    categoria_id=child.id,
                    atributo_id=inherited.id,
                    activo=False,
                ),
                CategoriaAtributo(
                    categoria_id=child.id,
                    atributo_id=bandwidth.id,
                    activo=True,
                ),
            ]
        )
        session.commit()
        client = _client(session)

        effective = client.get(
            f"/api/v1/categorias/{child.id}/atributos-efectivos"
        )
        assert effective.status_code == 200
        effective_items = effective.json()
        assert [item["nombre"] for item in effective_items] == [
            "Zeta almacenamiento",
            "Ancho de banda",
            "Marca",
        ]
        assert effective_items[0] == {
            "mapping_id": str(child_storage.id),
            "atributo_id": str(storage.id),
            "codigo": "almacenamiento",
            "nombre": "Zeta almacenamiento",
            "tipo_dato": "integer",
            "unidad": {
                "id": str(unit.id),
                "codigo": "GB",
                "nombre": "Gigabyte",
                "simbolo": "GB",
                "magnitud_codigo": "DATA_STORAGE",
            },
            "restricciones": {
                "allow_negative": False,
                "min_value": None,
                "max_value": None,
            },
            "select_options": None,
            "catalog_id": None,
            "obligatorio": True,
            "valor_default": None,
            "orden": 1,
            "categoria_origen": {"id": str(child.id), "nombre": "Child"},
            "profundidad": 0,
            "heredado": False,
        }
        assert effective_items[2]["categoria_origen"] == {
            "id": str(parent.id),
            "nombre": "Parent",
        }
        assert effective_items[2]["profundidad"] == 1
        assert effective_items[2]["heredado"] is True
        assert effective_items[2]["mapping_id"] == str(parent_inherited.id)

        own = client.get(f"/api/v1/categorias/{child.id}/atributos-propios")
        assert own.status_code == 200
        assert [item["nombre"] for item in own.json()] == [
            "Zeta almacenamiento",
            "Ancho de banda",
        ]
    engine.dispose()


def test_legacy_multi_category_scope_accepts_one_ancestry_and_rejects_sibling_branches() -> None:
    from fastapi import HTTPException

    from osiris.modules.inventario.categoria.service import CategoriaService

    engine = _build_test_engine()
    with Session(engine) as session:
        root = Categoria(nombre="Scope root", activo=True)
        session.add(root)
        session.flush()
        child = Categoria(nombre="Scope child", parent_id=root.id, activo=True)
        sibling = Categoria(nombre="Scope sibling", parent_id=root.id, activo=True)
        attribute = Atributo(
            nombre="Scope attribute",
            codigo="scope_attribute",
            tipo_dato=TipoDato.STRING,
            activo=True,
        )
        session.add_all([child, sibling, attribute])
        session.flush()
        parent_mapping = CategoriaAtributo(
            categoria_id=root.id,
            atributo_id=attribute.id,
            valor_default="parent",
            activo=True,
        )
        child_mapping = CategoriaAtributo(
            categoria_id=child.id,
            atributo_id=attribute.id,
            valor_default=None,
            activo=True,
        )
        sibling_mapping = CategoriaAtributo(
            categoria_id=sibling.id,
            atributo_id=attribute.id,
            valor_default="sibling",
            activo=True,
        )
        session.add_all([parent_mapping, child_mapping, sibling_mapping])
        session.commit()
        service = CategoriaService()

        resolved = service.get_atributos_heredados_por_categorias(
            session, [root.id, child.id]
        )
        assert len(resolved) == 1
        assert resolved[0]["mapping_id"] == child_mapping.id
        assert resolved[0]["valor_default"] is None

        with pytest.raises(HTTPException) as error:
            service.get_atributos_heredados_por_categorias(
                session, [child.id, sibling.id]
            )
        assert error.value.status_code == 409
        assert error.value.detail["code"] == "CATEGORY_ATTRIBUTE_SCOPE_AMBIGUOUS"
        assert error.value.detail["affected_ids"] == [str(child.id), str(sibling.id)]
    engine.dispose()

    def test_effective_endpoint_does_not_inherit_from_inactive_ancestor() -> None:
        engine = _build_test_engine()
        with Session(engine) as session:
            inactive_parent = Categoria(nombre="Inactive parent", activo=False)
            session.add(inactive_parent)
            session.flush()
            active_child = Categoria(
                nombre="Active child", parent_id=inactive_parent.id, activo=True
            )
            parent_attribute = Atributo(
                nombre="Inactive parent's attribute",
                codigo="inactive_parent_attribute",
                tipo_dato=TipoDato.STRING,
                activo=True,
            )
            child_attribute = Atributo(
                nombre="Active child's attribute",
                codigo="active_child_attribute",
                tipo_dato=TipoDato.STRING,
                activo=True,
            )
            session.add_all([active_child, parent_attribute, child_attribute])
            session.flush()
            session.add_all(
                [
                    CategoriaAtributo(
                        categoria_id=inactive_parent.id,
                        atributo_id=parent_attribute.id,
                        activo=True,
                    ),
                    CategoriaAtributo(
                        categoria_id=active_child.id,
                        atributo_id=child_attribute.id,
                        activo=True,
                    ),
                ]
            )
            session.commit()

            response = _client(session).get(
                f"/api/v1/categorias/{active_child.id}/atributos-efectivos"
            )

            assert response.status_code == 200
            assert [item["nombre"] for item in response.json()] == [
                "Active child's attribute"
            ]
        engine.dispose()
def test_assign_existing_reactivates_mapping_and_rejects_active_duplicate() -> None:
    engine = _build_test_engine()
    with Session(engine) as session:
        category = Categoria(nombre="Assignment category", activo=True)
        attribute = Atributo(
            nombre="Assignment attribute",
            codigo="assignment_attribute",
            tipo_dato=TipoDato.STRING,
            activo=True,
        )
        session.add_all([category, attribute])
        session.flush()
        mapping = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            orden=7,
            valor_default="old",
            activo=False,
        )
        session.add(mapping)
        session.commit()
        mapping_id = mapping.id
        client = _client(session)

        payload = {
            "atributo_id": str(attribute.id),
            "obligatorio": True,
            "valor_default": None,
        }
        preview = client.post(
            f"/api/v1/categorias/{category.id}/atributos/previsualizar",
            json=payload,
        )
        assert preview.status_code == 200, preview.text
        response = client.post(
            f"/api/v1/categorias/{category.id}/atributos",
            json={**payload, "precondicion_preview": preview.json()["precondicion_preview"]},
        )
        assert response.status_code == 201
        assert response.json()["mapping_id"] == str(mapping_id)
        assert response.json()["valor_default"] is None
        assert response.json()["orden"] == 7
        session.refresh(mapping)
        assert mapping.activo is True

        duplicate = client.post(
            f"/api/v1/categorias/{category.id}/atributos",
            json={"atributo_id": str(attribute.id)},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["code"] == "ATTRIBUTE_ALREADY_ASSIGNED"
        assert mapping.id == mapping_id
        audit_rows = session.exec(
            select(AuditLog).where(AuditLog.entidad_id == mapping_id)
        ).all()
        assert [row.accion for row in audit_rows] == [
            "REACTIVATE_CATEGORY_ATTRIBUTE"
        ]
    engine.dispose()


def test_deep_category_tree_uses_a_fixed_number_of_queries() -> None:
    engine = _build_test_engine()
    with Session(engine) as session:
        root = Categoria(nombre="Depth 0", activo=True)
        attribute = Atributo(
            nombre="Deep attribute",
            codigo="deep_attribute",
            tipo_dato=TipoDato.STRING,
            activo=True,
        )
        session.add_all([root, attribute])
        session.flush()
        session.add(
            CategoriaAtributo(
                categoria_id=root.id,
                atributo_id=attribute.id,
                activo=True,
            )
        )
        parent = root
        for depth in range(1, 41):
            child = Categoria(
                nombre=f"Depth {depth}", parent_id=parent.id, activo=True
            )
            session.add(child)
            session.flush()
            parent = child
        session.commit()

        statements: list[str] = []

        def capture_statement(
            _connection, _cursor, statement, _parameters, _context, _executemany
        ):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", capture_statement)
        tree = get_category_tree(session)
        event.remove(engine, "before_cursor_execute", capture_statement)

        node = tree[0]
        depth = 0
        while node.hijos:
            node = node.hijos[0]
            depth += 1
        assert depth == 40
        assert node.atributos_efectivos_count == 1
        assert len(statements) <= 3
    engine.dispose()

def test_category_creation_rejects_inactive_or_temporary_parents() -> None:
    from fastapi import HTTPException

    from osiris.modules.inventario.categoria.service import CategoriaService

    engine = _build_test_engine()
    with Session(engine) as session:
        inactive = Categoria(nombre="Inactive", activo=False)
        bucket = Categoria(nombre="Sin clasificar", is_default=True, activo=True)
        session.add_all([inactive, bucket])
        session.commit()

        with pytest.raises(HTTPException) as inactive_error:
            CategoriaService().create(
                session, {"nombre": "Child", "parent_id": inactive.id}
            )
        assert inactive_error.value.detail["code"] == "CATEGORY_PARENT_INACTIVE"

        with pytest.raises(HTTPException) as bucket_error:
            CategoriaService().create(
                session, {"nombre": "Child", "parent_id": bucket.id}
            )
        assert bucket_error.value.detail["code"] == "CATEGORY_DEFAULT_PROTECTED"
        assert session.exec(select(Categoria).where(Categoria.nombre == "Child")).all() == []
    engine.dispose()


def test_category_tree_requires_authenticated_catalog_read_permission() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/api/v1/categorias").status_code == 401
    assert client.get("/api/v1/categorias/arbol").status_code == 401
    category_id = uuid4()
    assert (
        client.get(f"/api/v1/categorias/{category_id}/atributos-efectivos").status_code
        == 401
    )
    assert (
        client.get(f"/api/v1/categorias/{category_id}/atributos-propios").status_code
        == 401
    )
    assert (
        client.post(
            f"/api/v1/categorias/{category_id}/atributos",
            json={"atributo_id": str(uuid4())},
        ).status_code
        == 401
    )


def test_category_write_contract_ignores_legacy_flag_and_read_aliases_projection() -> None:
    assert "es_padre" not in CategoriaCreate.model_json_schema()["properties"]
    created = CategoriaCreate.model_validate(
        {
            "nombre": "Leaf",
            "es_padre": True,
            "usuario_auditoria": "forged-actor",
        }
    )
    assert created.model_dump(exclude_unset=True) == {"nombre": "Leaf"}
    with pytest.raises(ValueError):
        CategoriaCreate.model_validate({"nombre": "Leaf", "es_padr": True})

    entity = Categoria(nombre="Leaf", es_padre=False, activo=True)
    read = CategoriaRead.model_validate(entity)
    assert read.tiene_hijos is False
    assert read.es_padre is False


def test_move_to_root_does_not_create_or_reclassify_a_b3_bucket() -> None:
    from tests.test_categoria_regla_b3 import _seed_categoria_hoja_con_dos_productos
    from osiris.modules.inventario.categoria.service import CategoriaService

    engine = _build_test_engine()
    with Session(engine) as session:
        parent, _ = _seed_categoria_hoja_con_dos_productos(session)
        child = CategoriaService().create(
            session,
            {"nombre": "Child", "parent_id": parent.id, "es_padre": False},
            confirmar_b3=True,
        )
        existing_buckets = session.exec(
            select(Categoria).where(
                Categoria.parent_id == parent.id,
                Categoria.is_default.is_(True),
            )
        ).all()
        assert len(existing_buckets) == 1
        bucket_id = existing_buckets[0].id

        moved = CategoriaService().update(session, child.id, {"parent_id": None})
        assert moved is not None and moved.parent_id is None
        buckets = session.exec(
            select(Categoria).where(Categoria.is_default.is_(True))
        ).all()
        assert [(bucket.id, bucket.parent_id) for bucket in buckets] == [
            (bucket_id, parent.id)
        ]
    engine.dispose()


def test_reactivation_route_returns_same_ordinary_category_identity() -> None:
    engine = _build_test_engine()
    with Session(engine) as session:
        category = Categoria(nombre="Historical", activo=False)
        session.add(category)
        session.commit()
        category_id = category.id

        response = _client(session).post(
            f"/api/v1/categorias/{category_id}/reactivar"
        )

        assert response.status_code == 200
        assert response.json()["id"] == str(category_id)
        assert response.json()["activo"] is True
        assert response.json()["tiene_hijos"] is False
    engine.dispose()


def test_b3_preview_requires_confirmation_and_reclassifies_only_after_valid_token() -> None:
    from tests.test_categoria_regla_b3 import _seed_categoria_hoja_con_dos_productos

    engine = _build_test_engine()
    with Session(engine) as session:
        parent, product_ids = _seed_categoria_hoja_con_dos_productos(session)
        client = _client(session)
        payload = {"nombre": "Child", "parent_id": str(parent.id)}

        preview = client.post("/api/v1/categorias/previsualizar", json=payload)
        assert preview.status_code == 200, preview.text
        preview_body = preview.json()
        assert preview_body["requiere_confirmacion"] is True
        assert preview_body["conteos"]["productos_directos"] == 2

        blocked = client.post("/api/v1/categorias", json=payload)
        assert blocked.status_code == 409
        assert blocked.json()["detail"]["code"] == "CATEGORY_CHANGE_REQUIRES_CONFIRMATION"
        assert not session.exec(
            select(Categoria).where(Categoria.parent_id == parent.id)
        ).all()

        created = client.post(
            "/api/v1/categorias",
            json={
                "payload": payload,
                "confirmar_b3": True,
                "precondicion_preview": preview_body["precondicion_preview"],
            },
        )
        assert created.status_code == 201, created.text
        bucket = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == parent.id)
            .where(Categoria.is_default.is_(True))
        ).one()
        moved = session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.categoria_id == bucket.id
            )
        ).all()
        assert {item.producto_id for item in moved} == set(product_ids)
    engine.dispose()


def test_b3_confirmation_rejects_changed_product_classification() -> None:
    from tests.test_categoria_regla_b3 import _seed_categoria_hoja_con_dos_productos

    engine = _build_test_engine()
    with Session(engine) as session:
        parent, _ = _seed_categoria_hoja_con_dos_productos(session)
        client = _client(session)
        payload = {"nombre": "Child", "parent_id": str(parent.id)}
        preview = client.post("/api/v1/categorias/previsualizar", json=payload)
        token = preview.json()["precondicion_preview"]
        added_product = Producto(
            nombre="Concurrent product",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            categoria_principal_id=parent.id,
            activo=True,
        )
        session.add(added_product)
        session.flush()
        session.add(
            ProductoCategoria(
                producto_id=added_product.id,
                categoria_id=parent.id,
            )
        )
        session.commit()

        response = client.post(
            "/api/v1/categorias",
            json={"payload": payload, "confirmar_b3": True, "precondicion_preview": token},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "CATALOG_PREVIEW_STALE"
        assert not session.exec(
            select(Categoria).where(Categoria.parent_id == parent.id)
        ).all()
    engine.dispose()


def test_moving_category_to_product_parent_uses_b3_preview_confirmation() -> None:
    from tests.test_categoria_regla_b3 import _seed_categoria_hoja_con_dos_productos

    engine = _build_test_engine()
    with Session(engine) as session:
        parent, product_ids = _seed_categoria_hoja_con_dos_productos(session)
        moving = Categoria(nombre="Moving category", activo=True)
        session.add(moving)
        session.commit()
        moving_id = moving.id
        parent_id = parent.id
        client = _client(session)
        payload = {"parent_id": str(parent_id)}

        preview = client.post(
            f"/api/v1/categorias/{moving_id}/previsualizar", json=payload
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["conteos"]["productos_directos"] == 2

        blocked = client.put(f"/api/v1/categorias/{moving_id}", json=payload)
        assert blocked.status_code == 409
        assert blocked.json()["detail"]["code"] == "CATEGORY_CHANGE_REQUIRES_CONFIRMATION"

        moved = client.put(
            f"/api/v1/categorias/{moving_id}",
            json={
                "payload": payload,
                "confirmar_b3": True,
                "precondicion_preview": preview.json()["precondicion_preview"],
            },
        )
        assert moved.status_code == 200, moved.text
        buckets = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == parent_id)
            .where(Categoria.is_default.is_(True))
        ).all()
        assert len(buckets) == 1
        assignments = session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.categoria_id == buckets[0].id
            )
        ).all()
        assert {item.producto_id for item in assignments} == set(product_ids)
    engine.dispose()