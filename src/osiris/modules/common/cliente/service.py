# src/osiris/modules/common/cliente/service.py
from __future__ import annotations

from fastapi import HTTPException
from uuid import UUID
from typing import Any
from sqlmodel import Session, select
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.domain.directory_service import DirectoryService
from .repository import ClienteRepository
from .models import ClienteCreate, ClienteRead, ClienteUpdate

from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.tipo_cliente.entity import TipoCliente


class ClienteService(DirectoryService):
    repo = ClienteRepository()
    read_model = ClienteRead
    create_model = ClienteCreate
    update_model = ClienteUpdate
    persona_field = "persona_id"
    unique_field = "persona_id"
    catalog_model = TipoCliente
    catalog_field = "tipo_cliente_id"
    catalog_name_field = "tipo_cliente_nombre"

    fk_models = {
        "persona_id": Persona,
        "tipo_cliente_id": TipoCliente,
    }

    def _active_type(self, session: Session, type_id: UUID | str | None) -> UUID:
        if type_id is None:
            raise HTTPException(status_code=422, detail="tipo_cliente_id es requerido")
        try:
            type_id = UUID(str(type_id))
        except ValueError as error:
            raise HTTPException(
                status_code=422, detail="tipo_cliente_id no valido"
            ) from error
        catalog = session.exec(
            select(TipoCliente)
            .where(TipoCliente.id == type_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            .with_for_update()
        ).first()
        if catalog is None:
            raise HTTPException(status_code=404, detail="TipoCliente no encontrado")
        if catalog.activo is False:
            raise HTTPException(status_code=409, detail="TipoCliente inactivo")
        return type_id

    def validate_create(self, data: dict[str, Any], session: Session) -> None:
        data["tipo_cliente_id"] = self._active_type(
            session, data.get("tipo_cliente_id")
        )

    def prepare_update(
        self, session: Session, current: Any, payload: dict[str, Any]
    ) -> dict[str, Any]:
        payload = self.immutable_persona(current, payload)
        if "tipo_cliente_id" in payload:
            payload["tipo_cliente_id"] = self._active_type(
                session, payload["tipo_cliente_id"]
            )
        return payload
