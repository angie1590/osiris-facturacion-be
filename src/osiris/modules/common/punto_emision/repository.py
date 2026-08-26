from __future__ import annotations

from typing import Optional
from uuid import UUID

from osiris.domain.repository import BaseRepository
from .entity import PuntoEmision

class PuntoEmisionRepository(BaseRepository):
    model = PuntoEmision

    def apply_filters(
        self,
        stmt,
        *,
        sucursal_id: Optional[UUID] = None,
        only_active: Optional[bool] = None,
        **kw,
    ):
        if sucursal_id:
            stmt = stmt.where(PuntoEmision.sucursal_id == sucursal_id)
        return stmt
