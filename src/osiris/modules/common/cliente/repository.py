# src/osiris/modules/common/cliente/repository.py
from __future__ import annotations

from osiris.domain.repository import BaseRepository
from .entity import Cliente

class ClienteRepository(BaseRepository):
    model = Cliente
