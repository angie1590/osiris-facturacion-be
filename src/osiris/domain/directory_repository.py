from __future__ import annotations

from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.domain.repository import BaseRepository
from osiris.modules.common.persona.entity import Persona


class DirectoryRepository(BaseRepository):
    persona_field: str | None = None
    search_fields: tuple[str, ...] = ()
    sort_fields: tuple[str, ...] = ()

    def get(self, session: Session, item_id: Any, *, lock: bool = False) -> Any:
        statement = (
            select(self.model)
            .where(self.model.id == item_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        )
        if lock:
            statement = statement.with_for_update()
        return session.exec(statement).first()

    def list(
        self,
        session: Session,
        *,
        only_active: bool | None = True,
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
        estado: str | None = None,
        sort_by: str = "creado_en",
        sort_direction: str = "desc",
        sort_order: str | None = None,
        order_by: Iterable[Any] | None = None,
        **filters: Any,
    ) -> tuple[list[Any], int]:
        direction = sort_order or sort_direction
        if estado not in {None, "activo", "inactivo"} or direction not in {
            "asc",
            "desc",
        }:
            raise HTTPException(status_code=422, detail="Estado u orden no valido")
        columns = {
            name: getattr(self.model, name)
            for name in ("id", "creado_en", "actualizado_en", *self.sort_fields)
        }
        statement = select(self.model)
        search = [getattr(self.model, field) for field in self.search_fields]
        if self.persona_field:
            statement = statement.join(
                Persona, getattr(self.model, self.persona_field) == Persona.id
            )
            for name in ("identificacion", "nombre", "apellido", "email", "telefono"):
                columns.setdefault(name, getattr(Persona, name))
                search.append(getattr(Persona, name))
        if sort_by not in columns:
            raise HTTPException(status_code=422, detail="Campo de orden no permitido")
        if estado is not None:
            statement = statement.where(self.model.activo == (estado == "activo"))
        elif only_active:
            statement = statement.where(self.model.activo.is_(True))
        if q and q.strip():
            term = (
                q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            statement = statement.where(
                or_(*(column.ilike(f"%{term}%", escape="\\") for column in search))
            )
        statement = statement.execution_options(
            **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
        )
        count = (
            select(func.count())
            .select_from(statement.subquery())
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        )
        total = int(session.execute(count).scalar_one())
        column = columns[sort_by]
        ordering = (
            tuple(order_by)
            if order_by is not None
            else (
                column.asc() if direction == "asc" else column.desc(),
                self.model.id.asc(),
            )
        )
        statement = statement.order_by(*ordering)
        return list(session.exec(statement.offset(offset).limit(limit)).all()), total
