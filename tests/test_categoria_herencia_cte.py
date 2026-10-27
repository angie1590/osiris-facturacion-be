from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Categoria.__table__,
            Unidad.__table__,
            Atributo.__table__,
            CategoriaAtributo.__table__,
        ],
    )
    return engine


def test_get_atributos_heredados_por_categoria_resuelve_conflicto_por_cercania():
    engine = _build_test_engine()
    service = CategoriaService()

    with Session(engine) as session:
        abuelo = Categoria(nombre="Abuelo", es_padre=True, activo=True, usuario_auditoria="test")
        session.add(abuelo)
        session.commit()
        session.refresh(abuelo)

        padre = Categoria(
            nombre="Padre",
            es_padre=True,
            parent_id=abuelo.id,
            activo=True,
            usuario_auditoria="test",
        )
        session.add(padre)
        session.commit()
        session.refresh(padre)

        hijo = Categoria(
            nombre="Hijo",
            es_padre=False,
            parent_id=padre.id,
            activo=True,
            usuario_auditoria="test",
        )
        session.add(hijo)
        session.commit()
        session.refresh(hijo)

        garantia = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            activo=True,
            usuario_auditoria="test",
        )
        session.add(garantia)
        session.commit()
        session.refresh(garantia)

        session.add(
            CategoriaAtributo(
                categoria_id=abuelo.id,
                atributo_id=garantia.id,
                obligatorio=False,
                orden=1,
                activo=True,
                usuario_auditoria="test",
            )
        )
        session.add(
            CategoriaAtributo(
                categoria_id=padre.id,
                atributo_id=garantia.id,
                obligatorio=True,
                orden=2,
                activo=True,
                usuario_auditoria="test",
            )
        )
        session.commit()

        result = service.get_atributos_heredados_por_categoria(session, hijo.id)

        assert len(result) == 1
        garantia_resuelta = result[0]
        assert garantia_resuelta["atributo_id"] == garantia.id
        assert garantia_resuelta["atributo_nombre"] == "Garantía"
        assert garantia_resuelta["obligatorio"] is True
        assert garantia_resuelta["categoria_origen_id"] == padre.id

        # Sin duplicados por atributo
        unique_ids = {item["atributo_id"] for item in result}
        assert len(unique_ids) == len(result)


def test_legacy_multi_category_resolution_accepts_ancestry_and_rejects_sibling_branches():
    engine = _build_test_engine()
    with Session(engine) as session:
        root = Categoria(nombre="Scope root", activo=True)
        session.add(root)
        session.flush()
        child = Categoria(nombre="Scope child", parent_id=root.id, activo=True)
        sibling = Categoria(nombre="Scope sibling", activo=True)
        attribute = Atributo(
            nombre="Scope attribute",
            tipo_dato=TipoDato.STRING,
            activo=True,
            usuario_auditoria="test",
        )
        session.add_all([child, sibling, attribute])
        session.flush()
        child_mapping = CategoriaAtributo(
            categoria_id=child.id,
            atributo_id=attribute.id,
            obligatorio=False,
            valor_default=None,
            activo=True,
        )
        session.add_all(
            [
                CategoriaAtributo(
                    categoria_id=root.id,
                    atributo_id=attribute.id,
                    obligatorio=False,
                    valor_default="root default",
                    activo=True,
                ),
                child_mapping,
            ]
        )
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
