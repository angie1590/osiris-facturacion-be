# src/osiris/modules/common/sucursal/repository.py
from __future__ import annotations
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.sql import Select
from sqlmodel import col

from osiris.domain.repository import BaseRepository
from .entity import Sucursal


class SucursalRepository(BaseRepository):
    model = Sucursal

    def apply_filters(
        self,
        stmt: Select[Any],
        *,
        empresa_id: Optional[UUID] = None,
        only_active: Optional[bool] = None,
        **kw: Any,
    ) -> Select[Any]:
        # Deja que la base aplique only_active y demás si ya lo hace;
        # si tu BaseRepository ya maneja only_active, no lo toques aquí.
        if empresa_id:
            stmt = stmt.where(col(Sucursal.empresa_id) == empresa_id)
        return stmt
