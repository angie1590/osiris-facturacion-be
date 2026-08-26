from __future__ import annotations

from uuid import UUID
from sqlalchemy import Column, ForeignKey
from sqlmodel import Field

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class ProveedorSociedad(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_proveedor_sociedad"

    # ---- Campos propios (se conservan los nombres) ----
    ruc: str = Field(nullable=False, unique=True, max_length=13)
    razon_social: str = Field(nullable=False)
    nombre_comercial: str | None = Field(default=None)
    direccion: str = Field(nullable=False)
    telefono: str | None = Field(default=None)  # validación en DTO
    email: str = Field(nullable=False)          # validación en DTO

    # FKs (sin relationship)
    tipo_contribuyente_id: str = Field(
        sa_column=Column(
            ForeignKey("aux_tipo_contribuyente.codigo"),
            nullable=False,
        ),
        max_length=2,
    )
    persona_contacto_id: UUID = Field(
        sa_column=Column(
            ForeignKey("tbl_persona.id"),
            nullable=False,
        )
    )
