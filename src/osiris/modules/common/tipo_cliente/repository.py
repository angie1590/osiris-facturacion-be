from __future__ import annotations

from osiris.domain.directory_repository import DirectoryRepository
from .entity import TipoCliente


class TipoClienteRepository(DirectoryRepository):
    model = TipoCliente
    search_fields = ("nombre",)
    sort_fields = ("nombre", "descuento")
