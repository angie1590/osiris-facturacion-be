# src/osiris/modules/common/persona/service.py
from __future__ import annotations


from osiris.domain.service import BaseService
from .repository import PersonaRepository


class PersonaService(BaseService):
    def __init__(self, repo: PersonaRepository | None = None) -> None:
        self.repo = repo or PersonaRepository()
