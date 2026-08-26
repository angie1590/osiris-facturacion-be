# src/osiris/modules/common/persona/entity.py
from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlmodel import Field

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class TipoIdentificacion(str, Enum):
    CEDULA = "CEDULA"
    RUC = "RUC"
    PASAPORTE = "PASAPORTE"


class Persona(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    """
    Entidad Persona alineada a SQLModel y a tus mixins.
    Mantiene los mismos campos que tu modelo anterior.
    """
    __tablename__ = "tbl_persona"

    tipo_identificacion: TipoIdentificacion = Field(
        sa_column=Column(
            # Enum nativo de Postgres con constraint, como en el modelo antiguo
            PgEnum(TipoIdentificacion, name="tipo_identificacion_enum", create_type=True),
            nullable=False,
            default=TipoIdentificacion.CEDULA,
        )
    )

    identificacion: str = Field(nullable=False, unique=True, index=True)

    # En tu modelo antiguo eran 'nombre' y 'apellido' (no nombres/apellidos):
    nombre: str = Field(nullable=False, max_length=120, index=True)
    apellido: str = Field(nullable=False, max_length=120, index=True)

    direccion: Optional[str] = Field(default=None, max_length=255)
    telefono: Optional[str] = Field(default=None, max_length=30)
    ciudad: Optional[str] = Field(default=None, max_length=120)
    email: Optional[str] = Field(default=None, max_length=120)
