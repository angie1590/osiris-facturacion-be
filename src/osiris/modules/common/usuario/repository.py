# src/osiris/modules/common/usuario/repository.py
from __future__ import annotations
from typing import Any
from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, select
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.domain.repository import BaseRepository
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.rol.entity import Rol
from .entity import Usuario
from .models import UsuarioRead


def list_directory_roles(session: Session, model: Any, read_model: Any, *, only_active: bool = True,
                         limit: int = 50, offset: int = 0, q: str | None = None, identificacion: str | None = None,
                         estado: str | None = None, sort_by: str = "creado_en", sort_order: str = "desc",
                         sort_direction: str | None = None,
                         empresa_id: Any = None) -> tuple[list[Any], int]:
    if sort_direction is not None:
        sort_order = sort_direction
    is_user = model is Usuario
    statement: Any = select(model, Persona).join(Persona, model.persona_id == Persona.id)
    if is_user:
        statement = statement.add_columns(Rol).join(Rol, model.rol_id == Rol.id)
    if estado not in {None, "activo", "inactivo"}:
        raise HTTPException(status_code=422, detail="Estado no permitido")
    if estado is not None:
        statement = statement.where(model.activo == (estado == "activo"))
    elif only_active:
        statement = statement.where(model.activo.is_(True))
    if empresa_id is not None and not is_user:
        statement = statement.where(model.empresa_id == empresa_id)
    if identificacion:
        statement = statement.where(func.upper(func.trim(Persona.identificacion)) == identificacion.strip().upper())
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        search_columns: list[Any] = [Persona.identificacion, Persona.nombre, Persona.apellido, Persona.email, Persona.telefono]
        if is_user:
            search_columns.extend([Usuario.username, Rol.nombre])
        statement = statement.where(or_(*(column.ilike(pattern) for column in search_columns)))
    columns = {field: getattr(model, field) for field in ("id", "creado_en", "actualizado_en", "activo")}
    columns.update({field: getattr(Persona, field) for field in ("identificacion", "nombre", "apellido")})
    if is_user:
        columns.update({"username": Usuario.username, "rol_nombre": Rol.nombre})
    else:
        columns.update({"salario": model.salario, "fecha_ingreso": model.fecha_ingreso, "fecha_salida": model.fecha_salida})
    if sort_by not in columns or sort_order not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="Orden no permitido")
    statement = statement.execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
    count = select(func.count()).select_from(statement.subquery()).execution_options(
        **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
    )
    total = int(session.execute(count).scalar_one())
    column = columns[sort_by]
    statement = statement.order_by(column.asc() if sort_order == "asc" else column.desc(), model.id).offset(offset).limit(limit)
    items = []
    for row in session.execute(statement).all():
        record, person = row[0], row[1]
        projection = {**record.model_dump(), "persona": person}
        if is_user:
            projection["rol_nombre"] = row[2].nombre
            projection["tiene_codigo_aprobacion"] = record.codigo_aprobacion_hash is not None
        items.append(read_model.model_validate(projection))
    return items, total

class UsuarioRepository(BaseRepository):
    model = Usuario

    def get(self, session: Session, item_id: Any, *, lock: bool = False) -> Usuario | None:
        statement = select(Usuario).where(Usuario.id == item_id).execution_options(
            **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
        )
        if lock:
            statement = statement.with_for_update()
        return session.exec(statement).first()

    def list(self, session: Session, **filters: Any) -> tuple[list[UsuarioRead], int]:
        return list_directory_roles(session, Usuario, UsuarioRead, **filters)
