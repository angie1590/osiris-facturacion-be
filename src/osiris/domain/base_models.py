# src/domain/base_models.py
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import event
from sqlmodel import SQLModel, Field

from osiris.core.audit_context import get_current_user_id


class BaseOSModel(SQLModel):
    """Modelo base Pydantic-only (no tabla)."""

class AuditMixin(SQLModel):
    creado_en: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    actualizado_en: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )
    created_by: Optional[str] = Field(default=None, max_length=255, index=True)
    updated_by: Optional[str] = Field(default=None, max_length=255, index=True)
    usuario_auditoria: Optional[str] = Field(default=None)

    # Alias estándar para auditoría transversal sin romper el esquema legado.
    @property
    def created_at(self) -> datetime:
        return self.creado_en

    @created_at.setter
    def created_at(self, value: datetime) -> None:
        self.creado_en = value

    @property
    def updated_at(self) -> datetime:
        return self.actualizado_en

    @updated_at.setter
    def updated_at(self, value: datetime) -> None:
        self.actualizado_en = value

class SoftDeleteMixin(SQLModel):
    activo: bool = Field(default=True, index=True)

class BaseTable(SQLModel, table=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)


@event.listens_for(BaseTable, "before_insert", propagate=True)
def _audit_before_insert(_mapper, _connection, target):
    now = datetime.utcnow()
    if hasattr(target, "creado_en"):
        target.creado_en = getattr(target, "creado_en", None) or now
    if hasattr(target, "actualizado_en"):
        target.actualizado_en = now

    user_id = get_current_user_id()
    legacy_actor = getattr(target, "usuario_auditoria", None) if hasattr(target, "usuario_auditoria") else None
    actor = user_id or legacy_actor

    if hasattr(target, "created_by") and not getattr(target, "created_by", None):
        target.created_by = actor
    if hasattr(target, "updated_by") and not getattr(target, "updated_by", None):
        target.updated_by = actor or getattr(target, "created_by", None)
    if hasattr(target, "usuario_auditoria") and not getattr(target, "usuario_auditoria", None):
        target.usuario_auditoria = actor or getattr(target, "updated_by", None)


@event.listens_for(BaseTable, "before_update", propagate=True)
def _audit_before_update(_mapper, _connection, target):
    if hasattr(target, "actualizado_en"):
        target.actualizado_en = datetime.utcnow()

    user_id = get_current_user_id()
    actor = user_id or getattr(target, "updated_by", None) or getattr(target, "usuario_auditoria", None)
    if actor and hasattr(target, "updated_by"):
        target.updated_by = actor
    if actor and hasattr(target, "usuario_auditoria"):
        target.usuario_auditoria = actor
