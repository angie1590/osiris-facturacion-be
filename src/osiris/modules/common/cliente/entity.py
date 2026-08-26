# src/osiris/modules/common/cliente/entity.py
from __future__ import annotations

from uuid import UUID
from sqlmodel import Field
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin

class Cliente(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_cliente"

    persona_id: UUID = Field(
        foreign_key="tbl_persona.id",
        nullable=False,
        unique=True,
        index=True,
    )

    tipo_cliente_id: UUID = Field(
        foreign_key="tbl_tipo_cliente.id",
        nullable=False,
        index=True,
    )
