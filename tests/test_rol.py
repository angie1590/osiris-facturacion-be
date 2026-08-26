from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from pydantic import BaseModel

# Repositorio/Servicio reales (no tocan BD porque mockeamos Session / repo)
from osiris.modules.common.rol.repository import RolRepository
from osiris.modules.common.rol.service import RolService
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.rol.models import RolUpdate


# ---------------------------
# Repositorio: create / update / delete (con Session mock)
# ---------------------------

def test_rol_repository_create_desde_dict_instancia_modelo_y_persiste():
    session = MagicMock()
    repo = RolRepository()

    payload = {"nombre": f"Rol-{uuid4().hex[:8]}", "descripcion": "Desc", "usuario_auditoria": "tester"}
    created = repo.create(session, payload)

    assert isinstance(created, Rol)
    assert created.nombre == payload["nombre"]
    session.add.assert_called_once()            # se envía a la sesión
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_rol_repository_create_desde_pydantic_instancia_modelo():
    session = MagicMock()
    repo = RolRepository()

    class RolCreateDTO(BaseModel):
        nombre: str
        descripcion: str | None = None
        usuario_auditoria: str | None = None

    dto = RolCreateDTO(nombre=f"Rol-{uuid4().hex[:8]}", descripcion="X", usuario_auditoria="tester")
    created = repo.create(session, dto)

    assert isinstance(created, Rol)
    assert created.nombre == dto.nombre
    session.add.assert_called_once()
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_rol_repository_update_desde_dict_actualiza_campos():
    session = MagicMock()
    repo = RolRepository()

    db_obj = Rol(nombre="Viejo", descripcion="d1", usuario_auditoria="tester")
    data = {"nombre": "Nuevo", "descripcion": "d2"}

    updated = repo.update(session, db_obj, data)

    assert updated.nombre == "Nuevo"
    assert updated.descripcion == "d2"
    session.add.assert_called_once_with(db_obj)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_rol_repository_update_desde_pydantic_exclude_unset():
    session = MagicMock()
    repo = RolRepository()

    db_obj = Rol(nombre="Original", descripcion=None, usuario_auditoria="tester")
    dto = RolUpdate(descripcion="Actualizado")  # solo cambia descripcion

    updated = repo.update(session, db_obj, dto)

    assert updated.nombre == "Original"
    assert updated.descripcion == "Actualizado"
    session.flush.assert_called_once()
    session.commit.assert_not_called()


def test_rol_repository_delete_logico_si_tiene_activo():
    session = MagicMock()
    repo = RolRepository()

    db_obj = Rol(nombre="X", descripcion=None, usuario_auditoria="tester", activo=True)
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

def test_rol_service_update_not_found_devuelve_none_y_no_actualiza():
    repo = MagicMock()
    repo.get.return_value = None

    service = RolService()
    service.repo = repo

    out = service.update(MagicMock(), item_id=uuid4(), data={"nombre": "X"})
    assert out is None
    repo.update.assert_not_called()


def test_rol_service_update_found_llama_repo_update():
    repo = MagicMock()
    repo.get.return_value = Rol(nombre="A", usuario_auditoria="tester")  # objeto existente
    repo.update.return_value = "UPDATED"

    service = RolService()
    service.repo = repo

    out = service.update(MagicMock(), item_id=uuid4(), data={"nombre": "B"})
    assert out == "UPDATED"
    repo.update.assert_called_once()


def test_rol_service_list_paginated_retorna_items_y_meta():
    repo = MagicMock()
    repo.list.return_value = (["r1", "r2"], 10)

    service = RolService()
    service.repo = repo

    items, meta = service.list_paginated(MagicMock(), limit=2, offset=4, only_active=True)

    assert items == ["r1", "r2"]
    assert meta.total == 10
    assert meta.limit == 2
    assert meta.offset == 4
    # dependiendo del total, has_more podría ser True o False; con 10 y offset 4 + limit 2 => True
    assert meta.has_more is True


# ---------------------------
# Verifica que update use model_dump(exclude_unset=True) cuando recibe Pydantic
# (es decir, que no sobreescriba con None campos no enviados)
# ---------------------------

def test_rol_repository_update_no_sobrescribe_campos_no_enviados():
    from unittest.mock import MagicMock
    from osiris.modules.common.rol.repository import RolRepository
    from osiris.modules.common.rol.entity import Rol
    from osiris.modules.common.rol.models import RolUpdate

    session = MagicMock()
    repo = RolRepository()

    # Estado inicial en DB
    db_obj = Rol(nombre="Original", descripcion="d1", usuario_auditoria="tester")

    # DTO que NO envía 'nombre' -> debe mantenerse
    partial = RolUpdate(descripcion="nueva")

    updated = repo.update(session, db_obj, partial)

    # Comportamiento esperado: solo cambia 'descripcion'
    assert updated.nombre == "Original"
    assert updated.descripcion == "nueva"

    # Persistencia llamada
    session.add.assert_called_once_with(db_obj)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()
