from osiris.domain.repository import BaseRepository
from .entity import Modulo


class ModuloRepository(BaseRepository):
    model = Modulo
