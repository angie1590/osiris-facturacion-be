from __future__ import annotations

from osiris.domain.repository import BaseRepository
from .entity import ProveedorSociedad


class ProveedorSociedadRepository(BaseRepository):
    model = ProveedorSociedad
