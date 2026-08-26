from __future__ import annotations

from osiris.domain.repository import BaseRepository
from .entity import TipoCliente


class TipoClienteRepository(BaseRepository):
    model = TipoCliente
