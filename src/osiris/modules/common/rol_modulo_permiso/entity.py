# src/osiris/modules/common/rol_modulo_permiso/entity.py
from __future__ import annotations
from uuid import UUID

from sqlmodel import Field, UniqueConstraint
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class RolModuloPermiso(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "roles_modulos_permisos"
    __table_args__ = (
        UniqueConstraint("rol_id", "modulo_id", name="uq_rol_modulo"),
    )

    rol_id: UUID = Field(
        foreign_key="tbl_rol.id",
        nullable=False,
        index=True,
        description="FK al rol"
    )
    modulo_id: UUID = Field(
        foreign_key="tbl_modulo.id",
        nullable=False,
        index=True,
        description="FK al módulo"
    )
    puede_leer: bool = Field(
        default=False,
        nullable=False,
        description="Permiso para operaciones GET"
    )
    puede_crear: bool = Field(
        default=False,
        nullable=False,
        description="Permiso para operaciones POST"
    )
    puede_actualizar: bool = Field(
        default=False,
        nullable=False,
        description="Permiso para operaciones PUT/PATCH"
    )
    puede_eliminar: bool = Field(
        default=False,
        nullable=False,
        description="Permiso para operaciones DELETE"
    )
