from typing import Optional
from sqlmodel import SQLModel, Field

class TipoContribuyente(SQLModel, table=True):
    __tablename__ = "aux_tipo_contribuyente"

    # Catálogo: clave corta como PK (evita UUID para llaves “de diccionario”)
    codigo: str = Field(primary_key=True, max_length=8)
    nombre: str = Field(nullable=False, max_length=120)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    activo: bool = Field(default=True, nullable=False)
