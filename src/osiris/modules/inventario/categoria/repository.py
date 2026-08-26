from __future__ import annotations

from osiris.domain.repository import BaseRepository
from .entity import Categoria


class CategoriaRepository(BaseRepository):
    model = Categoria
