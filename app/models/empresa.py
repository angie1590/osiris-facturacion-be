from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import IdentificationType


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(primary_key=True)
    ruc: Mapped[str] = mapped_column(String(13), unique=True, nullable=False, index=True)
    razon_social: Mapped[str] = mapped_column(String(300), nullable=False)
    nombre_comercial: Mapped[str | None] = mapped_column(String(300), nullable=True)
    identification_type: Mapped[IdentificationType] = mapped_column(
        Enum(IdentificationType), nullable=False, default=IdentificationType.ruc
    )
    obligado_contabilidad: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sucursales: Mapped[list["Sucursal"]] = relationship(back_populates="empresa", cascade="all, delete-orphan")


class Sucursal(Base):
    __tablename__ = "sucursales"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_establecimiento: Mapped[str] = mapped_column(String(3), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    empresa: Mapped["Empresa"] = relationship(back_populates="sucursales")
    puntos_emision: Mapped[list["PuntoEmision"]] = relationship(back_populates="sucursal", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("empresa_id", "codigo_establecimiento", name="uq_sucursal_empresa_codigo"),)


class PuntoEmision(Base):
    __tablename__ = "puntos_emision"

    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursales.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_punto_emision: Mapped[str] = mapped_column(String(3), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sucursal: Mapped["Sucursal"] = relationship(back_populates="puntos_emision")

    __table_args__ = (UniqueConstraint("sucursal_id", "codigo_punto_emision", name="uq_punto_emision_sucursal_codigo"),)
