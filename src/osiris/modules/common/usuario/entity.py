# src/osiris/modules/common/usuario/entity.py
from __future__ import annotations
from typing import Optional
from uuid import UUID
from sqlmodel import Field
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin

class Usuario(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_usuario"

    persona_id: UUID = Field(foreign_key="tbl_persona.id", nullable=False, unique=True)
    rol_id: UUID = Field(foreign_key="tbl_rol.id", nullable=False)

    username: str = Field(nullable=False, unique=True, index=True, max_length=120)
    password_hash: str = Field(nullable=False, max_length=255)
    requiere_cambio_password: bool = Field(default=True, nullable=False)

    usuario_auditoria: Optional[str] = Field(default=None, max_length=255)
