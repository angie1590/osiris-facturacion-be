# src/osiris/modules/inventario/bodega/repository.py
from __future__ import annotations

from osiris.domain.repository import BaseRepository
from .entity import Bodega


class BodegaRepository(BaseRepository):
    model = Bodega
