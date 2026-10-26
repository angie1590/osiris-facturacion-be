from __future__ import annotations

from osiris.domain.directory_repository import DirectoryRepository
from .entity import ProveedorSociedad


class ProveedorSociedadRepository(DirectoryRepository):
    model = ProveedorSociedad
    persona_field = "persona_contacto_id"
    search_fields = (
        "ruc",
        "razon_social",
        "nombre_comercial",
        "direccion",
        "email",
        "telefono",
    )
    sort_fields = (
        "ruc",
        "razon_social",
        "nombre_comercial",
        "tipo_contribuyente_id",
        "email",
        "telefono",
    )
