from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import Column, Table
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.core.db import get_session
from osiris.core.auth import get_current_usuario
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.router import assign_category_attribute_permission
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoCategoria,
    ProductoProveedorPersona,
    ProductoProveedorSociedad,
    TipoProducto,
)
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeo,
    ProductoAtributoValor,
)
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.producto.entity import ProductoBodega, ProductoImpuesto
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo
from tests.utils.product_permissions import (
    clear_product_permission_overrides,
    override_product_permissions,
)


def _ensure_fk_stub_targets_in_metadata() -> None:
    # Targets mínimos para crear tablas puente de proveedor usadas por get_producto_completo.
    if "tbl_proveedor_persona" not in SQLModel.metadata.tables:
        Table(
            "tbl_proveedor_persona",
            SQLModel.metadata,
            Column("id", sa.Uuid(), primary_key=True),
        )
    if "tbl_proveedor_sociedad" not in SQLModel.metadata.tables:
        Table(
            "tbl_proveedor_sociedad",
            SQLModel.metadata,
            Column("id", sa.Uuid(), primary_key=True),
        )


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _ensure_fk_stub_targets_in_metadata()
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AuditLog.__table__,
            TipoContribuyente.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            Rol.__table__,
            Bodega.__table__,
            CasaComercial.__table__,
            Unidad.__table__,
            Categoria.__table__,
            Atributo.__table__,
            CategoriaAtributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoBodega.__table__,
            ProductoImpuesto.__table__,
            ImpuestoCatalogo.__table__,
            ProductoProveedorPersona.__table__,
            ProductoProveedorSociedad.__table__,
            ProductoAtributoRemapeo.__table__,
            ProductoAtributoValor.__table__,
        ],
    )
    return engine


def _seed_data_for_producto_completo(session: Session):
    raiz = Categoria(nombre=f"Raiz-{uuid4().hex[:6]}", es_padre=True, usuario_auditoria="test")
    hija = Categoria(nombre=f"Hija-{uuid4().hex[:6]}", es_padre=False, parent_id=raiz.id, usuario_auditoria="test")

    garantia = Atributo(nombre=f"Garantia-{uuid4().hex[:6]}", tipo_dato=TipoDato.STRING, usuario_auditoria="test")
    peso = Atributo(nombre=f"Peso-{uuid4().hex[:6]}", tipo_dato=TipoDato.DECIMAL, usuario_auditoria="test")

    producto = Producto(
        nombre=f"Producto-{uuid4().hex[:6]}",
        descripcion="Detalle de prueba",
        codigo_barras=f"BC-{uuid4().hex[:8]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("99.99"),
        categoria_principal_id=hija.id,
        usuario_auditoria="test",
    )

    session.add_all([raiz, hija, garantia, peso, producto])
    session.flush()

    session.add_all(
        [
            CategoriaAtributo(
                categoria_id=raiz.id,
                atributo_id=garantia.id,
                obligatorio=False,
                orden=1,
                usuario_auditoria="test",
            ),
            CategoriaAtributo(
                categoria_id=hija.id,
                atributo_id=garantia.id,
                obligatorio=True,
                orden=2,
                usuario_auditoria="test",
            ),
            CategoriaAtributo(
                categoria_id=hija.id,
                atributo_id=peso.id,
                obligatorio=False,
                orden=3,
                usuario_auditoria="test",
            ),
                ProductoCategoria(producto_id=producto.id, categoria_id=raiz.id),
            ProductoAtributoValor(
                producto_id=producto.id,
                atributo_id=garantia.id,
                valor_string="24 meses",
                usuario_auditoria="test",
            ),
        ]
    )
    session.commit()

    return producto.id, garantia.id, peso.id, hija.id, raiz.id


def _seed_data_conflicto_herencia_abuelo_padre_hijo(session: Session):
    abuelo = Categoria(nombre=f"Abuelo-{uuid4().hex[:6]}", es_padre=True, usuario_auditoria="test")
    padre = Categoria(nombre=f"Padre-{uuid4().hex[:6]}", es_padre=True, parent_id=abuelo.id, usuario_auditoria="test")
    hijo = Categoria(nombre=f"Hijo-{uuid4().hex[:6]}", es_padre=False, parent_id=padre.id, usuario_auditoria="test")

    garantia = Atributo(nombre=f"Garantia-{uuid4().hex[:6]}", tipo_dato=TipoDato.STRING, usuario_auditoria="test")
    producto = Producto(
        nombre=f"Producto-{uuid4().hex[:6]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("55.00"),
        categoria_principal_id=hijo.id,
        usuario_auditoria="test",
    )

    session.add_all([abuelo, padre, hijo, garantia, producto])
    session.flush()

    session.add_all(
        [
            CategoriaAtributo(
                categoria_id=abuelo.id,
                atributo_id=garantia.id,
                obligatorio=False,  # opcional en abuelo
                orden=1,
                usuario_auditoria="test",
            ),
            CategoriaAtributo(
                categoria_id=padre.id,
                atributo_id=garantia.id,
                obligatorio=True,  # obligatorio en padre (más específico que abuelo)
                orden=2,
                usuario_auditoria="test",
            ),
            ProductoCategoria(producto_id=producto.id, categoria_id=hijo.id),
        ]
    )
    session.commit()
    return producto.id, garantia.id


def _seed_data_soft_delete_categoria_atributo(session: Session):
    categoria = Categoria(nombre=f"Categoria-{uuid4().hex[:6]}", es_padre=False, usuario_auditoria="test")
    peso = Atributo(nombre=f"Peso-{uuid4().hex[:6]}", tipo_dato=TipoDato.STRING, usuario_auditoria="test")
    producto = Producto(
        nombre=f"Producto-{uuid4().hex[:6]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("49.90"),
        categoria_principal_id=categoria.id,
        usuario_auditoria="test",
    )

    session.add_all([categoria, peso, producto])
    session.flush()

    vinculo = CategoriaAtributo(
        categoria_id=categoria.id,
        atributo_id=peso.id,
        obligatorio=False,
        orden=1,
        usuario_auditoria="test",
    )

    session.add_all(
        [
            vinculo,
            ProductoCategoria(producto_id=producto.id, categoria_id=categoria.id),
            ProductoAtributoValor(
                producto_id=producto.id,
                atributo_id=peso.id,
                valor_string="2kg",
                usuario_auditoria="test",
            ),
        ]
    )
    session.commit()

    return producto.id, peso.id, vinculo.id


def _seed_data_cambio_familia_producto(session: Session):
    categoria_a = Categoria(nombre=f"Laptops-{uuid4().hex[:6]}", es_padre=False, usuario_auditoria="test")
    categoria_b = Categoria(nombre=f"Televisores-{uuid4().hex[:6]}", es_padre=False, usuario_auditoria="test")
    atributo_x = Atributo(nombre=f"RAM-{uuid4().hex[:6]}", tipo_dato=TipoDato.STRING, usuario_auditoria="test")
    atributo_y = Atributo(nombre=f"Resolucion-{uuid4().hex[:6]}", tipo_dato=TipoDato.STRING, usuario_auditoria="test")
    producto = Producto(
        nombre=f"Producto-{uuid4().hex[:6]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("799.00"),
        categoria_principal_id=categoria_a.id,
        usuario_auditoria="test",
    )

    session.add_all([categoria_a, categoria_b, atributo_x, atributo_y, producto])
    session.flush()

    session.add_all(
        [
            CategoriaAtributo(
                categoria_id=categoria_a.id,
                atributo_id=atributo_x.id,
                obligatorio=False,
                orden=1,
                usuario_auditoria="test",
            ),
            CategoriaAtributo(
                categoria_id=categoria_b.id,
                atributo_id=atributo_y.id,
                obligatorio=False,
                orden=1,
                usuario_auditoria="test",
            ),
            ProductoCategoria(producto_id=producto.id, categoria_id=categoria_a.id),
            ProductoAtributoValor(
                producto_id=producto.id,
                atributo_id=atributo_x.id,
                valor_string="Hola",
                usuario_auditoria="test",
            ),
        ]
    )
    session.commit()

    return producto.id, categoria_b.id, atributo_x.id, atributo_y.id


def _seed_company_scope(session: Session, product_ids):
    session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
    company = Empresa(
        razon_social="Empresa EAV",
        ruc="1790012345001",
        direccion_matriz="Direccion",
        tipo_contribuyente_id="01",
        usuario_auditoria="test",
        activo=True,
    )
    role = Rol(nombre="admin", usuario_auditoria="test", activo=True)
    session.add_all([company, role])
    session.flush()
    branch = Sucursal(
        codigo="001",
        nombre="Matriz",
        direccion="Direccion",
        es_matriz=True,
        empresa_id=company.id,
        usuario_auditoria="test",
        activo=True,
    )
    session.add(branch)
    session.flush()
    warehouse = Bodega(
        codigo_bodega=f"B-{uuid4().hex[:6]}",
        nombre_bodega="Bodega EAV",
        empresa_id=company.id,
        sucursal_id=branch.id,
        usuario_auditoria="test",
        activo=True,
    )
    session.add(warehouse)
    session.flush()
    session.add_all(
        [
            ProductoBodega(
                producto_id=product_id,
                bodega_id=warehouse.id,
                cantidad=Decimal("0"),
                usuario_auditoria="test",
                activo=True,
            )
            for product_id in product_ids
        ]
    )
    session.commit()
    return company.id, role.id


def _install_test_dependencies(engine: sa.Engine, role_id):
    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_usuario] = lambda: SimpleNamespace(rol_id=role_id)
    override_product_permissions(app, role_id)


def test_get_producto_completo_incluye_atributos_heredados_y_valores_persistidos():
    engine = _build_test_engine()

    with Session(engine) as session:
        producto_id, garantia_id, peso_id, categoria_id, raiz_id = _seed_data_for_producto_completo(session)
        company_id, role_id = _seed_company_scope(session, [producto_id])

    _install_test_dependencies(engine, role_id)
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/productos/{producto_id}", headers={"X-Empresa-Id": str(company_id)})
            assert response.status_code == 200
            body = response.json()

            assert "atributos" in body
            assert body["categoria_principal"]["id"] == str(categoria_id)
            assert [item["id"] for item in body["categoria_ruta"]] == [str(raiz_id), str(categoria_id)]
            assert [item["id"] for item in body["categorias"]] == [str(categoria_id)]
            assert body["descripcion"] == "Detalle de prueba"
            assert body["codigo_barras"].startswith("BC-")
            assert body["bodegas"]
            assert body["bodegas"][0]["bodega_id"] == body["bodegas"][0]["id"]
            assert "cantidad" in body["bodegas"][0]
            atributos = body["atributos"]
            assert isinstance(atributos, list)
            assert len(atributos) == 2

            by_id = {item["atributo"]["id"]: item for item in atributos}
            assert str(garantia_id) in by_id
            assert str(peso_id) in by_id
            assert len(by_id) == 2  # sin duplicados

            garantia = by_id[str(garantia_id)]
            assert garantia["atributo"]["tipo_dato"] == "string"
            assert garantia["atributo"]["categoria_origen"]["id"] == str(categoria_id)
            assert garantia["valor"] == "24 meses"
            assert garantia["obligatorio"] is True  # gana la categoría más cercana

            peso = by_id[str(peso_id)]
            assert peso["atributo"]["tipo_dato"] == "decimal"
            assert peso["valor"] is None
            assert peso["obligatorio"] is False

            list_response = client.get(
                "/api/v1/productos",
                headers={"X-Empresa-Id": str(company_id)},
            )
            assert list_response.status_code == 200
            listed = list_response.json()["items"]
            assert len(listed) == 1
            assert [item["id"] for item in listed[0]["categorias"]] == [str(categoria_id)]
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_usuario, None)
        clear_product_permission_overrides(app)


def test_get_producto_completo_rechaza_fk_ausente_aunque_exista_bridge_legacy():
    engine = _build_test_engine()
    with Session(engine) as session:
        producto_id, *_ = _seed_data_for_producto_completo(session)
        product = session.get(Producto, producto_id)
        assert product is not None
        product.categoria_principal_id = None
        session.add(product)
        session.commit()
        assert session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.producto_id == producto_id
            )
        ).first() is not None
        company_id, role_id = _seed_company_scope(session, [producto_id])

    _install_test_dependencies(engine, role_id)
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/productos/{producto_id}",
                headers={"X-Empresa-Id": str(company_id)},
            )

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "PRODUCT_CATEGORY_REQUIRED"
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_usuario, None)
        clear_product_permission_overrides(app)


def test_get_producto_completo_expone_error_estable_si_falla_resolucion_atributos(monkeypatch):
    engine = _build_test_engine()
    with Session(engine) as session:
        producto_id, *_ = _seed_data_for_producto_completo(session)
        company_id, role_id = _seed_company_scope(session, [producto_id])

    def fail_attribute_resolution(*_args, **_kwargs):
        raise RuntimeError("resolver unavailable")

    monkeypatch.setattr(
        CategoriaService,
        "get_atributos_heredados_por_categorias",
        fail_attribute_resolution,
    )
    _install_test_dependencies(engine, role_id)
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/productos/{producto_id}",
                headers={"X-Empresa-Id": str(company_id)},
            )

            assert response.status_code == 500
            assert response.json()["detail"]["code"] == "PRODUCT_ATTRIBUTE_RESOLUTION_FAILED"
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_usuario, None)
        clear_product_permission_overrides(app)


def test_get_producto_detalle_conflicto_herencia_abuelo_padre_hijo_gana_mas_especifico():
    engine = _build_test_engine()

    with Session(engine) as session:
        producto_id, garantia_id = _seed_data_conflicto_herencia_abuelo_padre_hijo(session)
        company_id, role_id = _seed_company_scope(session, [producto_id])

    _install_test_dependencies(engine, role_id)
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/productos/{producto_id}", headers={"X-Empresa-Id": str(company_id)})
            assert response.status_code == 200
            body = response.json()
            atributos = body.get("atributos", [])
            by_id = {item["atributo"]["id"]: item for item in atributos}

            assert str(garantia_id) in by_id
            assert by_id[str(garantia_id)]["obligatorio"] is True
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_usuario, None)
        clear_product_permission_overrides(app)


def test_list_productos_retorna_metadata_basica_sin_detalle_de_atributos():
    engine = _build_test_engine()
    with Session(engine) as session:
        producto_id, _garantia_id, _peso_id, categoria_id, _raiz_id = _seed_data_for_producto_completo(session)
        company_id, role_id = _seed_company_scope(session, [producto_id])

    _install_test_dependencies(engine, role_id)
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/productos?limit=50&offset=0&only_active=true", headers={"X-Empresa-Id": str(company_id)})
            assert response.status_code == 200
            payload = response.json()

            assert "items" in payload and isinstance(payload["items"], list)
            assert len(payload["items"]) >= 1
            item = payload["items"][0]

            assert {
                "id",
                "nombre",
                "tipo",
                "pvp",
                "cantidad",
                "categoria_principal",
                "categoria_ruta",
                "categorias",
            }.issubset(item)
            assert item["categoria_principal"]["id"] == item["categoria_ruta"][-1]["id"]
            assert item["categoria_principal"]["id"] == str(categoria_id)
            assert isinstance(item["categorias"], list)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_usuario, None)
        clear_product_permission_overrides(app)


def test_openapi_documenta_categoria_principal_ruta_y_metadatos_efectivos():
    schemas = app.openapi()["components"]["schemas"]

    assert {"categoria_principal", "categoria_ruta"}.issubset(
        schemas["ProductoCompletoRead"]["properties"]
    )
    assert {"descripcion", "codigo_barras"}.issubset(
        schemas["ProductoCompletoRead"]["properties"]
    )
    assert {"categoria_principal", "categoria_ruta"}.issubset(
        schemas["ProductoListadoRead"]["properties"]
    )
    assert {
        "codigo",
        "unidad_id",
        "unidad",
        "restricciones",
        "categoria_origen_id",
        "categoria_origen",
        "heredado",
    }.issubset(schemas["AtributoNested"]["properties"])
    assert {"id", "bodega_id", "cantidad"}.issubset(
        schemas["BodegaNested"]["properties"]
    )


def test_contextual_remove_category_attribute_hides_product_and_deactivates_eav():
    engine = _build_test_engine()
    with Session(engine) as session:
        producto_id, peso_id, vinculo_id = _seed_data_soft_delete_categoria_atributo(session)
        mapping = session.get(CategoriaAtributo, vinculo_id)
        assert mapping is not None
        categoria_id = mapping.categoria_id
        company_id, role_id = _seed_company_scope(session, [producto_id])

    _install_test_dependencies(engine, role_id)
    actor = SimpleNamespace(id=uuid4(), rol_id=role_id)
    app.dependency_overrides[assign_category_attribute_permission] = lambda: actor
    try:
        with TestClient(app) as client:
            headers = {"X-Empresa-Id": str(company_id)}
            before = client.get(f"/api/v1/productos/{producto_id}", headers=headers)
            assert before.status_code == 200
            atributos_before = before.json().get("atributos", [])
            by_id_before = {item["atributo"]["id"]: item for item in atributos_before}
            assert str(peso_id) in by_id_before
            assert by_id_before[str(peso_id)]["valor"] == "2kg"

            preview = client.post(
                f"/api/v1/categorias/{categoria_id}/atributos/{vinculo_id}/previsualizar-remocion",
                headers=headers,
            )
            assert preview.status_code == 200, preview.text
            assert preview.json()["conteos"]["valores_desactivados"] == 1
            delete_resp = client.request(
                "DELETE",
                f"/api/v1/categorias/{categoria_id}/atributos/{vinculo_id}",
                headers=headers,
                json={
                    "confirmar": True,
                    "precondicion_preview": preview.json()["precondicion_preview"],
                },
            )
            assert delete_resp.status_code == 200, delete_resp.text
            assert delete_resp.json() == {
                "mapping_id": str(vinculo_id),
                "valores_desactivados": 1,
            }

            after = client.get(f"/api/v1/productos/{producto_id}", headers=headers)
            assert after.status_code == 200
            atributos_after = after.json().get("atributos", [])
            by_id_after = {item["atributo"]["id"]: item for item in atributos_after}
            assert str(peso_id) not in by_id_after

        with Session(engine) as session:
            vinculo_db = session.exec(
                select(CategoriaAtributo)
                .where(CategoriaAtributo.id == vinculo_id)
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).first()
            assert vinculo_db is not None
            assert vinculo_db.activo is False

            eav_db = session.exec(
                select(ProductoAtributoValor)
                .where(ProductoAtributoValor.producto_id == producto_id)
                .where(ProductoAtributoValor.atributo_id == peso_id)
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).first()
            assert eav_db is not None
            assert eav_db.valor_string == "2kg"
            assert eav_db.activo is False
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_usuario, None)
        clear_product_permission_overrides(app)
        app.dependency_overrides.pop(assign_category_attribute_permission, None)


def test_cambio_categoria_oculta_atributo_huerfano_pero_conserva_historico_eav():
    engine = _build_test_engine()
    with Session(engine) as session:
        producto_id, categoria_b_id, atributo_x_id, atributo_y_id = _seed_data_cambio_familia_producto(session)
        company_id, role_id = _seed_company_scope(session, [producto_id])

    _install_test_dependencies(engine, role_id)
    try:
        with TestClient(app) as client:
            headers = {"X-Empresa-Id": str(company_id)}
            before = client.get(f"/api/v1/productos/{producto_id}", headers=headers)
            assert before.status_code == 200
            atributos_before = before.json().get("atributos", [])
            by_id_before = {item["atributo"]["id"]: item for item in atributos_before}
            assert str(atributo_x_id) in by_id_before
            assert by_id_before[str(atributo_x_id)]["valor"] == "Hola"

            update_resp = client.put(
                f"/api/v1/productos/{producto_id}",
                json={"categoria_ids": [str(categoria_b_id)]},
                headers=headers,
            )
            assert update_resp.status_code == 200

            after = client.get(f"/api/v1/productos/{producto_id}", headers=headers)
            assert after.status_code == 200
            atributos_after = after.json().get("atributos", [])
            by_id_after = {item["atributo"]["id"]: item for item in atributos_after}

            assert str(atributo_x_id) not in by_id_after
            assert str(atributo_y_id) in by_id_after
            assert by_id_after[str(atributo_y_id)]["valor"] is None

        with Session(engine) as session:
            eav_x = session.exec(
                select(ProductoAtributoValor)
                .where(ProductoAtributoValor.producto_id == producto_id)
                .where(ProductoAtributoValor.atributo_id == atributo_x_id)
            ).first()
            assert eav_x is not None
            assert eav_x.valor_string == "Hola"
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_usuario, None)
        clear_product_permission_overrides(app)
