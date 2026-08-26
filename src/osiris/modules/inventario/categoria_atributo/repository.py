# src/osiris/modules/inventario/categoria_atributo/repository.py
from __future__ import annotations

from osiris.domain.repository import BaseRepository
from .entity import CategoriaAtributo

class CategoriaAtributoRepository(BaseRepository):
    model = CategoriaAtributo
