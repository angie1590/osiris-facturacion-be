from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import Column, Table
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoCategoria,
    ProductoProveedorPersona,
    ProductoProveedorSociedad,
    TipoProducto,
)
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor


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
            CasaComercial.__table__,
            Categoria.__table__,
            Atributo.__table__,
            CategoriaAtributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoProveedorPersona.__table__,
            ProductoProveedorSociedad.__table__,
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
        tipo=TipoProducto.BIEN,
        pvp=Decimal("99.99"),
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
            ProductoCategoria(producto_id=producto.id, categoria_id=hija.id),
            ProductoAtributoValor(
                producto_id=producto.id,
                atributo_id=garantia.id,
                valor_string="24 meses",
                usuario_auditoria="test",
            ),
        ]
    )
    session.commit()

    return producto.id, garantia.id, peso.id


def _seed_data_conflicto_herencia_abuelo_padre_hijo(session: Session):
    abuelo = Categoria(nombre=f"Abuelo-{uuid4().hex[:6]}", es_padre=True, usuario_auditoria="test")
    padre = Categoria(nombre=f"Padre-{uuid4().hex[:6]}", es_padre=True, parent_id=abuelo.id, usuario_auditoria="test")
    hijo = Categoria(nombre=f"Hijo-{uuid4().hex[:6]}", es_padre=False, parent_id=padre.id, usuario_auditoria="test")

    garantia = Atributo(nombre=f"Garantia-{uuid4().hex[:6]}", tipo_dato=TipoDato.STRING, usuario_auditoria="test")
    producto = Producto(
        nombre=f"Producto-{uuid4().hex[:6]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("55.00"),
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


def test_get_producto_completo_incluye_atributos_heredados_y_valores_persistidos():
    engine = _build_test_engine()

    with Session(engine) as session:
        producto_id, garantia_id, peso_id = _seed_data_for_producto_completo(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/productos/{producto_id}")
            assert response.status_code == 200
            body = response.json()

            assert "atributos" in body
            atributos = body["atributos"]
            assert isinstance(atributos, list)
            assert len(atributos) == 2

            by_id = {item["atributo"]["id"]: item for item in atributos}
            assert str(garantia_id) in by_id
            assert str(peso_id) in by_id
            assert len(by_id) == 2  # sin duplicados

            garantia = by_id[str(garantia_id)]
            assert garantia["atributo"]["tipo_dato"] == "string"
            assert garantia["valor"] == "24 meses"
            assert garantia["obligatorio"] is True  # gana la categoría más cercana

            peso = by_id[str(peso_id)]
            assert peso["atributo"]["tipo_dato"] == "decimal"
            assert peso["valor"] is None
            assert peso["obligatorio"] is False
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_get_producto_detalle_conflicto_herencia_abuelo_padre_hijo_gana_mas_especifico():
    engine = _build_test_engine()

    with Session(engine) as session:
        producto_id, garantia_id = _seed_data_conflicto_herencia_abuelo_padre_hijo(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/productos/{producto_id}")
            assert response.status_code == 200
            body = response.json()
            atributos = body.get("atributos", [])
            by_id = {item["atributo"]["id"]: item for item in atributos}

            assert str(garantia_id) in by_id
            assert by_id[str(garantia_id)]["obligatorio"] is True
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_list_productos_retorna_metadata_basica_sin_detalle_de_atributos():
    engine = _build_test_engine()
    with Session(engine) as session:
        _seed_data_for_producto_completo(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/productos?limit=50&offset=0&only_active=true")
            assert response.status_code == 200
            payload = response.json()

            assert "items" in payload and isinstance(payload["items"], list)
            assert len(payload["items"]) >= 1
            item = payload["items"][0]

            assert set(item.keys()) == {"id", "nombre", "tipo", "pvp", "cantidad"}
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_soft_delete_categoria_atributo_oculta_en_producto_y_conserva_valor_eav():
    engine = _build_test_engine()
    with Session(engine) as session:
        producto_id, peso_id, vinculo_id = _seed_data_soft_delete_categoria_atributo(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            before = client.get(f"/api/v1/productos/{producto_id}")
            assert before.status_code == 200
            atributos_before = before.json().get("atributos", [])
            by_id_before = {item["atributo"]["id"]: item for item in atributos_before}
            assert str(peso_id) in by_id_before
            assert by_id_before[str(peso_id)]["valor"] == "2kg"

            delete_resp = client.delete(f"/api/v1/categorias-atributos/{vinculo_id}")
            assert delete_resp.status_code == 204

            after = client.get(f"/api/v1/productos/{producto_id}")
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
            ).first()
            assert eav_db is not None
            assert eav_db.valor_string == "2kg"
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_cambio_categoria_oculta_atributo_huerfano_pero_conserva_historico_eav():
    engine = _build_test_engine()
    with Session(engine) as session:
        producto_id, categoria_b_id, atributo_x_id, atributo_y_id = _seed_data_cambio_familia_producto(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            before = client.get(f"/api/v1/productos/{producto_id}")
            assert before.status_code == 200
            atributos_before = before.json().get("atributos", [])
            by_id_before = {item["atributo"]["id"]: item for item in atributos_before}
            assert str(atributo_x_id) in by_id_before
            assert by_id_before[str(atributo_x_id)]["valor"] == "Hola"

            update_resp = client.put(
                f"/api/v1/productos/{producto_id}",
                json={"categoria_ids": [str(categoria_b_id)]},
            )
            assert update_resp.status_code == 200

            after = client.get(f"/api/v1/productos/{producto_id}")
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
