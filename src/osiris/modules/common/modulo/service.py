from osiris.domain.service import BaseService
from .repository import ModuloRepository


class ModuloService(BaseService):
    repo = ModuloRepository()
