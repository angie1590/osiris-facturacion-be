from __future__ import annotations

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

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
