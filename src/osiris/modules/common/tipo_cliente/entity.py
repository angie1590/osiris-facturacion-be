from __future__ import annotations

from decimal import Decimal

from sqlmodel import Field
from sqlalchemy import CheckConstraint, Column
from sqlalchemy.types import Numeric

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class TipoCliente(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    """
    Catálogo de tipo de cliente.
    Mantiene exactamente los campos del modelo anterior:
      - id (UUID) -> provisto por BaseTable
      - nombre: str (unique, not null)
      - descuento: Numeric(5,2) (not null)
    """
    __tablename__ = "tbl_tipo_cliente"

    nombre: str = Field(nullable=False, unique=True, max_length=255, index=True)
    descuento: Decimal = Field(
        sa_column=Column(Numeric(5, 2), nullable=False)
    )
    __table_args__ = (
        CheckConstraint("descuento >= 0 AND descuento <= 100", name="ck_descuento_rango"),
    )
