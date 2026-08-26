from osiris.domain.repository import BaseRepository
from .entity import RolModuloPermiso


class RolModuloPermisoRepository(BaseRepository):
    model = RolModuloPermiso
