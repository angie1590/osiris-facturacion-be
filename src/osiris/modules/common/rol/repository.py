from osiris.domain.repository import BaseRepository
from .entity import Rol

class RolRepository(BaseRepository):
    model = Rol