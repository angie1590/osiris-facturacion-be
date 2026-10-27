from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, Index, String, Table
from sqlmodel import Field

from osiris.domain.base_models import AuditMixin, BaseTable, SoftDeleteMixin
from osiris.utils.catalog_index_expressions import normalized_lower_trim


class Unidad(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __table__: ClassVar[Table]
    __tablename__ = "tbl_unidad"
    __table_args__ = tuple(
        CheckConstraint(
            f"length(trim({campo}, ' \t\n\r\v\f')) > 0 AND length({campo}) <= {limite}",
            name=f"ck_tbl_unidad_{campo}_contenido",
        )
        for campo, limite in (
            ("codigo", 64),
            ("nombre", 120),
            ("simbolo", 32),
            ("magnitud_codigo", 64),
        )
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    codigo: str = Field(nullable=False, max_length=64)
    nombre: str = Field(nullable=False, max_length=120)
    simbolo: str = Field(
        max_length=32,
        sa_column=Column(
            String(32, collation="C").with_variant(String(32, collation="BINARY"), "sqlite"),
            nullable=False,
        ),
    )
    magnitud_codigo: str = Field(nullable=False, max_length=64)
    es_sistema: bool = Field(default=False, nullable=False)
    activo: bool = Field(default=True, nullable=False, index=True)


Unidad.__table__.append_constraint(Index(
    "uq_tbl_unidad_codigo_normalizado",
    normalized_lower_trim("codigo"),
    unique=True,
))
Index("uq_tbl_unidad_simbolo_exacto", Unidad.__table__.c.simbolo, unique=True)
