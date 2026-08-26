from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import IdentificationType, TipoPersona


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo: Mapped[TipoPersona] = mapped_column(Enum(TipoPersona), nullable=False)
    identificacion_tipo: Mapped[IdentificationType] = mapped_column(
        Enum(IdentificationType), nullable=False, default=IdentificationType.ruc
    )
    identificacion: Mapped[str] = mapped_column(String(20), nullable=False)
    razon_social: Mapped[str] = mapped_column(String(300), nullable=False)
    nombre_comercial: Mapped[str | None] = mapped_column(String(300), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __mapper_args__ = {
        "polymorphic_on": tipo,
        "polymorphic_abstract": True,
    }


class Cliente(Persona):
    __mapper_args__ = {"polymorphic_identity": TipoPersona.cliente}


class Proveedor(Persona):
    __mapper_args__ = {"polymorphic_identity": TipoPersona.proveedor}
