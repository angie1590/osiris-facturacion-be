from osiris.domain.service import BaseService
from .entity import Modulo
from .repository import ModuloRepository


class ModuloService(BaseService[Modulo]):
    repo = ModuloRepository()
