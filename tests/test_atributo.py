from __future__ import annotations

from unittest.mock import MagicMock

from osiris.modules.inventario.atributo.repository import AtributoRepository
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato


def test_atributo_repository_create_y_update():
    session = MagicMock()
    repo = AtributoRepository()

    created = repo.create(session, {"nombre": "color", "tipo_dato": TipoDato.STRING})
    assert isinstance(created, Atributo)
    session.add.assert_called_once()
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()

    # update parcial
    created.nombre = "color"
    updated = repo.update(session, created, {"nombre": "color2"})
    assert updated.nombre == "color2"
    assert session.flush.call_count == 2
