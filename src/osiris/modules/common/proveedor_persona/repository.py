from __future__ import annotations

from osiris.domain.repository import BaseRepository
from .entity import ProveedorPersona


class ProveedorPersonaRepository(BaseRepository):
    model = ProveedorPersona