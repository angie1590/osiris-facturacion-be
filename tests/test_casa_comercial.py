from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from pydantic import BaseModel

# Repositorio/Servicio reales (no tocan BD porque mockeamos Session / repo)
from osiris.modules.inventario.casa_comercial.repository import CasaComercialRepository
from osiris.modules.inventario.casa_comercial.service import CasaComercialService
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.casa_comercial.models import CasaComercialUpdate


# ---------------------------
# Repositorio: create / update / delete (con Session mock)
# ---------------------------

def test_casa_comercial_repository_create_desde_dict_instancia_modelo_y_persiste():
    session = MagicMock()
    repo = CasaComercialRepository()

    payload = {"nombre": f"Casa-{uuid4().hex[:8]}", "usuario_auditoria": "tester"}
    created = repo.create(session, payload)

    assert isinstance(created, CasaComercial)
    assert created.nombre == payload["nombre"]
    session.add.assert_called_once()            # se envía a la sesión
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_casa_comercial_repository_create_desde_pydantic_instancia_modelo():
    session = MagicMock()
    repo = CasaComercialRepository()

    class CasaComercialCreateDTO(BaseModel):
        nombre: str
        usuario_auditoria: str | None = None

    dto = CasaComercialCreateDTO(nombre=f"Casa-{uuid4().hex[:8]}", usuario_auditoria="tester")
    created = repo.create(session, dto)

    assert isinstance(created, CasaComercial)
    assert created.nombre == dto.nombre
    session.add.assert_called_once()
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_casa_comercial_repository_update_desde_dict_actualiza_campos():
    session = MagicMock()
    repo = CasaComercialRepository()

    db_obj = CasaComercial(nombre="Viejo", usuario_auditoria="tester")
    data = {"nombre": "Nuevo"}

    updated = repo.update(session, db_obj, data)

    assert updated.nombre == "Nuevo"
    session.add.assert_called_once_with(db_obj)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_casa_comercial_repository_update_desde_pydantic_exclude_unset():
    session = MagicMock()
    repo = CasaComercialRepository()

    db_obj = CasaComercial(nombre="Original", usuario_auditoria="tester")
    dto = CasaComercialUpdate(nombre="Actualizado")

    updated = repo.update(session, db_obj, dto)

    assert updated.nombre == "Actualizado"
    session.flush.assert_called_once()
    session.commit.assert_not_called()


def test_casa_comercial_repository_delete_logico_si_tiene_activo():
    session = MagicMock()
    repo = CasaComercialRepository()

    db_obj = CasaComercial(nombre="X", usuario_auditoria="tester", activo=True)
    ok = repo.delete(session, db_obj)

    assert ok is True
    assert db_obj.activo is False                 # borrado lógico
    session.add.assert_called_once_with(db_obj)
    session.delete.assert_not_called()
    session.flush.assert_called_once()
    session.commit.assert_not_called()


# ---------------------------
# Servicio: update / list_paginated (mock de repo)
# ---------------------------

def test_casa_comercial_service_update_not_found_devuelve_none_y_no_actualiza():
    repo = MagicMock()
    repo.get.return_value = None

    service = CasaComercialService()
    service.repo = repo

    out = service.update(MagicMock(), item_id=uuid4(), data={"nombre": "X"})
    assert out is None
    repo.update.assert_not_called()


def test_casa_comercial_service_update_found_llama_repo_update():
    repo = MagicMock()
    repo.get.return_value = CasaComercial(nombre="A", usuario_auditoria="tester")  # objeto existente
    repo.update.return_value = "UPDATED"

    service = CasaComercialService()
    service.repo = repo

    out = service.update(MagicMock(), item_id=uuid4(), data={"nombre": "B"})
    assert out == "UPDATED"
    repo.update.assert_called_once()


def test_casa_comercial_service_list_paginated_retorna_items_y_meta():
    repo = MagicMock()
    repo.list.return_value = (["c1", "c2"], 10)

    service = CasaComercialService()
    service.repo = repo

    items, meta = service.list_paginated(MagicMock(), limit=2, offset=4, only_active=True)

    assert items == ["c1", "c2"]
    assert meta.total == 10
    assert meta.limit == 2
    assert meta.offset == 4
    assert meta.has_more is True


# ---------------------------
# Verifica que update use model_dump(exclude_unset=True) cuando recibe Pydantic
# (es decir, que no sobreescriba con None campos no enviados)
# ---------------------------

def test_casa_comercial_repository_update_no_sobrescribe_campos_no_enviados():
    from unittest.mock import MagicMock
    from osiris.modules.inventario.casa_comercial.repository import CasaComercialRepository
    from osiris.modules.inventario.casa_comercial.entity import CasaComercial
    from osiris.modules.inventario.casa_comercial.models import CasaComercialUpdate

    session = MagicMock()
    repo = CasaComercialRepository()

    # Estado inicial en DB
    db_obj = CasaComercial(nombre="Original", usuario_auditoria="tester")

    # DTO que NO envía 'nombre' -> debe mantenerse
    partial = CasaComercialUpdate()

    updated = repo.update(session, db_obj, partial)

    # Comportamiento esperado: mantiene el nombre original
    assert updated.nombre == "Original"

    # Persistencia llamada
    session.add.assert_called_once_with(db_obj)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()
