# src/osiris/modules/common/cliente/repository.py
from __future__ import annotations

from osiris.domain.directory_repository import DirectoryRepository
from .entity import Cliente

class ClienteRepository(DirectoryRepository):
    model = Cliente
    persona_field = "persona_id"
    sort_fields = ("tipo_cliente_id",)
