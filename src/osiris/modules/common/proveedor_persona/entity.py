from __future__ import annotations

from uuid import UUID
from typing import Optional
from sqlmodel import Field, Column  # Relationship no usado
from sqlalchemy import String

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class ProveedorPersona(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_proveedor_persona"

    # PK heredada: id: UUID
    # Auditoría/activo heredados de mixins

    nombre_comercial: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))

    # FK a aux_tipo_contribuyente.codigo (PK tipo_contribuyente = código 2 chars)
    tipo_contribuyente_id: str = Field(
        max_length=2,
        foreign_key="aux_tipo_contribuyente.codigo",
    )
    persona_id: UUID = Field(
        max_length=13,
        foreign_key="tbl_persona.id",
    )
