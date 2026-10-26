# src/osiris/modules/common/persona/repository.py
from __future__ import annotations

from typing import Any
from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.sql import Select
from sqlmodel import col

from osiris.domain.repository import BaseRepository
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService
from .entity import Persona


class PersonaRepository(BaseRepository):
    model = Persona

    def apply_filters(self, stmt: Select[Any], *, only_active: bool | None = None, identificacion: str | None = None,
                      q: str | None = None, estado: str | None = None, sort_by: str | None = None,
                      sort_direction: str = "asc", **filters: Any) -> Select[Any]:
        if estado is not None:
            if estado not in {"activo", "inactivo"}:
                raise HTTPException(status_code=422, detail="Estado no permitido")
            stmt = stmt.where(col(Persona.activo).is_(estado == "activo"))
        elif only_active:
            stmt = stmt.where(col(Persona.activo).is_(True))
        if not only_active or estado == "inactivo":
            stmt = stmt.execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        if identificacion is not None:
            normalized = ValidacionCedulaRucService.normalizar_identificacion(identificacion)
            stmt = stmt.where(func.upper(func.trim(Persona.identificacion)) == normalized)
        if q and q.strip():
            value = q.strip().lower()
            stmt = stmt.where(or_(*[
                func.lower(column).contains(value, autoescape=True)
                for column in (Persona.identificacion, Persona.nombre, Persona.apellido, Persona.email, Persona.telefono)
            ]))
        allowed_sort = {name: getattr(Persona, name) for name in (
            "identificacion", "nombre", "apellido", "email", "telefono", "creado_en", "actualizado_en",
        )}
        if sort_direction not in {"asc", "desc"} or (sort_by is not None and sort_by not in allowed_sort):
            raise HTTPException(status_code=422, detail="Orden no permitido")
        column = allowed_sort[sort_by or "nombre"]
        return stmt.order_by(column.desc() if sort_direction == "desc" else column.asc(), col(Persona.id).asc())
