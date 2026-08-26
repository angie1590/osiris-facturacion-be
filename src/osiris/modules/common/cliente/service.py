# src/osiris/modules/common/cliente/service.py
from __future__ import annotations

from sqlmodel import Session
from uuid import UUID
from typing import Any

from osiris.domain.service import BaseService
from .repository import ClienteRepository

from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.tipo_cliente.entity import TipoCliente

class ClienteService(BaseService):
    repo = ClienteRepository()

    fk_models = {
        "persona_id": Persona,
        "tipo_cliente_id": TipoCliente,
    }

    def update(self, session: Session, item_id: UUID, data: Any):
        data = self._ensure_dict(data)
        data.pop("persona_id", None)
        return super().update(session, item_id, data)
