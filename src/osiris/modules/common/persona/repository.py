# src/osiris/modules/common/persona/repository.py
from __future__ import annotations

from osiris.domain.repository import BaseRepository
from .entity import Persona


class PersonaRepository(BaseRepository):
    model = Persona
    # Sin overrides: hereda list/create/update/delete estándar.
