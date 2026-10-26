from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.sql import Select
from sqlmodel import col
from osiris.domain.repository import BaseRepository
from .entity import PuntoEmision

class PuntoEmisionRepository(BaseRepository):
    model = PuntoEmision

    def apply_filters(
        self,
        stmt: Select[Any],
        *,
        sucursal_id: Optional[UUID] = None,
        only_active: Optional[bool] = None,
        **kw: Any,
    ) -> Select[Any]:
        if sucursal_id:
            stmt = stmt.where(col(PuntoEmision.sucursal_id) == sucursal_id)
        return stmt
