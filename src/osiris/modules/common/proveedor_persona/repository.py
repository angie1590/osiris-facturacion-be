from __future__ import annotations

from osiris.domain.directory_repository import DirectoryRepository
from .entity import ProveedorPersona


class ProveedorPersonaRepository(DirectoryRepository):
    model = ProveedorPersona
    persona_field = "persona_id"
    search_fields = ("nombre_comercial",)
    sort_fields = ("nombre_comercial", "tipo_contribuyente_id")
