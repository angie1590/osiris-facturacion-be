# src/osiris/modules/common/empleado/repository.py
from __future__ import annotations
from typing import Any
from sqlmodel import Session

from osiris.domain.repository import BaseRepository
from .entity import Empleado
from .models import EmpleadoRead
from osiris.modules.common.usuario.repository import list_directory_roles


class EmpleadoRepository(BaseRepository):
    model = Empleado

    def list(self, session: Session, **filters: Any) -> tuple[list[EmpleadoRead], int]:
        return list_directory_roles(session, Empleado, EmpleadoRead, **filters)
